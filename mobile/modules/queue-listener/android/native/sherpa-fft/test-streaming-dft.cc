// Copyright (c) 2026 CueBell contributors. SPDX-License-Identifier: Apache-2.0
// ReferenceDft is extracted verbatim from the SHA-verified upstream header.
#include "reference-dft.h"
#include "streaming-dft.h"
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <new>
#include <stdexcept>
#include <string>

static size_t allocations = 0;
void *operator new(size_t n) {
  ++allocations;
  if (void *p = std::malloc(n ? n : 1)) return p;
  throw std::bad_alloc();
}
void *operator new[](size_t n) { return ::operator new(n); }
void operator delete(void *p) noexcept { std::free(p); }
void operator delete[](void *p) noexcept { std::free(p); }
void operator delete(void *p, size_t) noexcept { std::free(p); }
void operator delete[](void *p, size_t) noexcept { std::free(p); }

static double max_forward = 0, max_inverse = 0, max_overlap = 0;
static uint32_t seed = 0x5eed1234;
float Random() {
  seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5;
  return static_cast<float>(static_cast<int32_t>(seed)) / 2147483648.0f;
}
void Check(const std::vector<float> &actual, const std::vector<float> &expected,
           const char *label, double &maximum, double absolute = 2e-8) {
  if (actual.size() != expected.size()) throw std::runtime_error("shape mismatch");
  for (size_t i = 0; i < actual.size(); ++i) {
    double error = std::abs(static_cast<double>(actual[i]) - expected[i]);
    maximum = std::max(maximum, error);
    if (!std::isfinite(actual[i]) || error > absolute + 2e-7 * std::abs(expected[i])) {
      std::cerr << label << " sample " << i << " actual=" << actual[i]
                << " expected=" << expected[i] << " error=" << error << '\n';
      throw std::runtime_error("transform tolerance exceeded");
    }
  }
}

void Cases(int n) {
  ReferenceDft reference(n);
  sherpa_onnx::StreamingDft candidate(n);
  std::vector<float> input(n), actual(2 * (n / 2 + 1)), expected(actual.size());
  std::vector<float> restored(n), baseline(n);
  constexpr double pi = 3.14159265358979323846;
  for (int pattern = 0; pattern < 13; ++pattern) {
    std::fill(input.begin(), input.end(), 0);
    for (int i = 0; i < n; ++i) {
      switch (pattern) {
        case 0: break;  // silence
        case 1: input[i] = i == 0 ? 1 : 0; break;
        case 2: input[i] = i == n - 1 ? -1 : 0; break;
        case 3: input[i] = i == n / 2 ? 0.5f : 0; break;
        case 4: input[i] = 0.75f; break;  // DC
        case 5: input[i] = (i & 1) ? -1 : 1; break;  // Nyquist
        case 6: input[i] = std::sin(2 * pi * 7 * i / n); break;
        case 7: input[i] = std::cos(2 * pi * 3.25 * i / n); break;
        case 8: input[i] = std::sin(2 * pi * (n / 2 - 1) * i / n); break;
        case 9: input[i] = Random(); break;
        case 10: input[i] = Random() * 1e-7f; break;
        case 11: input[i] = Random() * 1e-35f; break;
        case 12: input[i] = i & 1 ? -1 : 32767.0f / 32768; break;
      }
    }
    reference.Forward(input.data(), expected.data());
    candidate.Forward(input.data(), actual.data());
    Check(actual, expected, "forward", max_forward);
    // Test inverse separately on identical spectra, then round trip with each
    // implementation's own spectrum to catch sign/scaling/layout errors.
    reference.Inverse(expected.data(), baseline.data());
    candidate.Inverse(expected.data(), restored.data());
    Check(restored, baseline, "inverse", max_inverse);
    candidate.Inverse(actual.data(), restored.data());
    Check(restored, baseline, "round-trip", max_inverse);
    if (n % 2 == 0) Check(restored, input, "identity", max_inverse, 2e-7);
  }
  for (int trial = 0; trial < 32; ++trial) {
    for (auto &x : expected) x = Random();
    // DC/Nyquist imaginary values must be ignored, exactly as upstream does.
    expected[1] = 123;
    if (n % 2 == 0) expected[n + 1] = -321;
    reference.Inverse(expected.data(), baseline.data());
    candidate.Inverse(expected.data(), restored.data());
    Check(restored, baseline, "arbitrary-spectrum", max_inverse);
  }
  size_t before = allocations;
  for (int i = 0; i < 128; ++i) {
    candidate.Forward(input.data(), actual.data());
    candidate.Inverse(actual.data(), restored.data());
  }
  if (allocations != before) throw std::runtime_error("per-call FFT allocation");
}

template <class Transform>
std::vector<float> Overlap(const std::vector<float> &input, Transform &fft) {
  // Same periodic Hann -> float sqrt and OLA operations as the pinned frontend.
  constexpr int n = 512, hop = 256;
  std::vector<float> analysis(n), overlap(n), window(n), fft_in(n), spectrum(n + 2), time(n), result;
  for (int i = 0; i < n; ++i) {
    window[i] = static_cast<float>(0.5 - 0.5 * std::cos(2 * 3.14159265358979323846 * i / n));
    window[i] = std::sqrt(window[i]);
  }
  for (size_t offset = 0; offset < input.size(); offset += hop) {
    std::move(analysis.begin() + hop, analysis.end(), analysis.begin());
    std::copy_n(input.data() + offset, hop, analysis.data() + hop);
    for (int i = 0; i < n; ++i) fft_in[i] = analysis[i] * window[i];
    fft.Forward(fft_in.data(), spectrum.data());
    // Fixed frequency mask exercises non-identity output, including DC/Nyquist.
    for (int k = 0; k <= n / 2; ++k) {
      float gain = 0.2f + 0.8f * k / (n / 2);
      spectrum[2 * k] *= gain; spectrum[2 * k + 1] *= gain;
    }
    fft.Inverse(spectrum.data(), time.data());
    std::move(overlap.begin() + hop, overlap.end(), overlap.begin());
    std::fill(overlap.begin() + hop, overlap.end(), 0);
    for (int i = 0; i < n; ++i) overlap[i] += time[i] * window[i];
    if (offset) result.insert(result.end(), overlap.begin(), overlap.begin() + hop);
  }
  return result;
}

template <class Transform>
double Timing(Transform &transform) {
  std::vector<float> input(512), spectrum(514), output(512);
  for (auto &x : input) x = Random();
  auto start = std::chrono::steady_clock::now();
  for (int i = 0; i < 1000; ++i) {
    transform.Forward(input.data(), spectrum.data());
    transform.Inverse(spectrum.data(), output.data());
  }
  auto end = std::chrono::steady_clock::now();
  volatile float keep = output[17]; (void)keep;
  // Two forward/inverse pairs are performed for each 512-sample capture frame.
  return std::chrono::duration<double, std::micro>(end - start).count() / 500;
}

int main() {
  for (int n : {2, 4, 8, 32, 256, 512, 1024, 480, 9}) Cases(n);
  for (int n : {1, 0, -1}) {
    try { sherpa_onnx::StreamingDft invalid(n); throw std::runtime_error("accepted invalid N"); }
    catch (const std::invalid_argument &) {}
  }
  ReferenceDft reference(512);
  sherpa_onnx::StreamingDft candidate(512);
  std::vector<float> input(512 * 80);
  for (auto &x : input) x = Random();
  auto baseline = Overlap(input, reference), actual = Overlap(input, candidate);
  if (actual.size() != input.size() - 256) throw std::runtime_error("startup alignment changed");
  Check(actual, baseline, "windowed overlap", max_overlap);
  auto repeated = Overlap(input, candidate);
  if (actual != repeated) throw std::runtime_error("scratch leaked between streams");
  sherpa_onnx::StreamingDft fresh(512);
  if (actual != Overlap(input, fresh)) throw std::runtime_error("fresh state mismatch");
  std::cout << std::setprecision(12)
            << "PASS: 9 sizes, 13 signals/size, 32 arbitrary spectra/size, allocation guard, 160-hop overlap/reset\n"
            << "forward_max_abs=" << max_forward << "\ninverse_max_abs=" << max_inverse
            << "\noverlap_max_abs=" << max_overlap << '\n'
            << "host_only_dft_us_per_512_samples=" << Timing(reference) << '\n'
            << "host_only_fft_us_per_512_samples=" << Timing(candidate) << '\n';
}
