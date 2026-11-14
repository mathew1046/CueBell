// Copyright (c) 2026 CueBell contributors. SPDX-License-Identifier: Apache-2.0
// Actual pinned native GTCRN implementation + original/patched streaming STFT.
#include "reference-gtcrn.h"
#include "sherpa-onnx/csrc/online-speech-denoiser-gtcrn-impl.h"
#include <cmath>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

int16_t Pcm(float v) {
  return static_cast<int16_t>(std::max(-32768.0, std::min(32767.0, std::floor(v * 32768.0 + 0.5))));
}

int main(int argc, char **argv) {
  if (argc != 3) throw std::runtime_error("usage: gtcrn-fft-regression MODEL INPUT_PCM16");
  std::ifstream input(argv[2], std::ios::binary);
  if (!input) throw std::runtime_error("could not open PCM");
  std::vector<int16_t> pcm;
  int16_t sample;
  while (input.read(reinterpret_cast<char *>(&sample), sizeof(sample))) pcm.push_back(sample);
  if (pcm.size() < 512 || pcm.size() % 512) throw std::runtime_error("expected complete 512-sample frames");
  sherpa_onnx::OnlineSpeechDenoiserConfig config;
  config.model.gtcrn.model = argv[1];
  config.model.num_threads = 1;
  config.model.provider = "cpu";
  sherpa_onnx::ReferenceGtcrn reference(config);
  sherpa_onnx::OnlineSpeechDenoiserGtcrnImpl candidate(config);
  std::vector<float> frame(512), first_pass;
  double max_error = 0, squared_error = 0, output_energy = 0;
  int max_pcm_error = 0;
  size_t compared = 0, differing_pcm = 0, nonzero_output_pcm = 0;
  for (int pass = 0; pass < 2; ++pass) {
    reference.Reset(); candidate.Reset();
    size_t cursor = 0;
    for (size_t offset = 0; offset < pcm.size(); offset += 512) {
      for (size_t i = 0; i < 512; ++i) frame[i] = pcm[offset + i] / 32768.0f;
      auto old_output = reference.Run(frame.data(), 512, 16000);
      auto new_output = candidate.Run(frame.data(), 512, 16000);
      const size_t expected = offset ? 512 : 256;
      if (old_output.sample_rate != 16000 || new_output.sample_rate != 16000 ||
          old_output.samples.size() != expected || new_output.samples.size() != expected) {
        throw std::runtime_error("framing/alignment changed");
      }
      for (size_t i = 0; i < expected; ++i) {
        float a = old_output.samples[i], b = new_output.samples[i];
        double error = std::abs(static_cast<double>(a) - b);
        max_error = std::max(max_error, error);
        squared_error += error * error;
        output_energy += static_cast<double>(b) * b;
        nonzero_output_pcm += Pcm(b) != 0;
        int pcm_error = std::abs(static_cast<int>(Pcm(a)) - Pcm(b));
        max_pcm_error = std::max(max_pcm_error, pcm_error);
        differing_pcm += pcm_error != 0;
        ++compared;
        if (!std::isfinite(b) || error > 2e-5 || pcm_error > 1) {
          throw std::runtime_error("end-to-end tolerance exceeded (2e-5 / one PCM16 LSB)");
        }
        if (pass == 0) first_pass.push_back(b);
        else if (first_pass[cursor] != b) throw std::runtime_error("reset did not reproduce exact output/state");
        ++cursor;
      }
    }
    auto old_tail = reference.Flush(), new_tail = candidate.Flush();
    if (old_tail.samples.size() != 256 || new_tail.samples.size() != 256) {
      throw std::runtime_error("flush alignment changed");
    }
    for (size_t i = 0; i < 256; ++i) {
      if (std::abs(old_tail.samples[i] - new_tail.samples[i]) > 2e-5) throw std::runtime_error("flush mismatch");
    }
  }
  std::cout.precision(12);
  std::cout << "PASS: actual native GTCRN, original/patched frontend, two exact-reset passes\n"
            << "frames_per_pass=" << pcm.size() / 512 << " compared_samples=" << compared
            << " max_float_error=" << max_error << " rms_float_error=" << std::sqrt(squared_error / compared)
            << " max_pcm16_lsb_error=" << max_pcm_error << " differing_pcm16_samples=" << differing_pcm
            << " nonzero_output_pcm16_samples=" << nonzero_output_pcm
            << " output_rms=" << std::sqrt(output_energy / compared) << '\n';
}
