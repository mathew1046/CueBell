// Copyright (c) 2026 CueBell contributors
// SPDX-License-Identifier: Apache-2.0
// CueBell modification for sherpa-onnx 2.0.1. Not an official upstream binary.
// The non-power-of-two fallback retains Xiaomi's original StreamingDft math
// (Copyright (c) 2026 Xiaomi Corporation, Apache-2.0).
#ifndef CUEBELL_SHERPA_STREAMING_DFT_H_
#define CUEBELL_SHERPA_STREAMING_DFT_H_

#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace sherpa_onnx {

// One owner at a time, just like the surrounding stateful streaming denoiser.
// Plans and scratch are allocated once. Forward/Inverse allocate nothing.
class StreamingDft {
 public:
  explicit StreamingDft(int32_t n_fft)
      : n_fft_(n_fft), num_bins_(n_fft / 2 + 1),
        radix2_(n_fft >= 2 && (n_fft & (n_fft - 1)) == 0) {
    if (n_fft < 2) throw std::invalid_argument("n_fft must be at least 2");
    constexpr double kPi = 3.14159265358979323846;
    if (radix2_) {
      real_.resize(n_fft_);
      imag_.resize(n_fft_);
      reverse_.resize(n_fft_);
      cos_f_.resize(n_fft_ / 2);
      sin_f_.resize(n_fft_ / 2);
      int32_t bits = 0;
      for (int32_t n = n_fft_; n > 1; n >>= 1) ++bits;
      for (int32_t i = 0; i < n_fft_; ++i) {
        uint32_t value = i, reversed = 0;
        for (int32_t b = 0; b < bits; ++b) {
          reversed = (reversed << 1) | (value & 1);
          value >>= 1;
        }
        reverse_[i] = reversed;
      }
      for (int32_t k = 0; k < n_fft_ / 2; ++k) {
        double angle = 2.0 * kPi * k / n_fft_;
        cos_f_[k] = std::cos(angle);
        sin_f_[k] = std::sin(angle);
      }
    } else {
      // Preserve upstream behavior for other sizes, including its existing
      // odd-size inverse convention (the highest positive bin is omitted).
      cos_f_.resize(static_cast<size_t>(num_bins_) * n_fft_);
      sin_f_.resize(cos_f_.size());
      cos_i_.resize(cos_f_.size());
      sin_i_.resize(cos_f_.size());
      for (int32_t k = 0; k < num_bins_; ++k) {
        for (int32_t n = 0; n < n_fft_; ++n) {
          double angle = 2.0 * kPi * k * n / n_fft_;
          double c = std::cos(angle), s = std::sin(angle);
          cos_f_[k * n_fft_ + n] = c;
          sin_f_[k * n_fft_ + n] = s;
          cos_i_[n * num_bins_ + k] = c;
          sin_i_[n * num_bins_ + k] = s;
        }
      }
    }
  }

  void Forward(const float *input, float *output) const {
    if (!radix2_) {
      for (int32_t k = 0; k != num_bins_; ++k) {
        double real = 0, imag = 0;
        const double *p_cos = cos_f_.data() + k * n_fft_;
        const double *p_sin = sin_f_.data() + k * n_fft_;
        for (int32_t n = 0; n != n_fft_; ++n) {
          double v = input[n];
          real += v * p_cos[n];
          imag -= v * p_sin[n];
        }
        output[2 * k] = static_cast<float>(real);
        output[2 * k + 1] = static_cast<float>(imag);
      }
      return;
    }
    for (int32_t n = 0; n < n_fft_; ++n) {
      real_[reverse_[n]] = input[n];
      imag_[reverse_[n]] = 0;
    }
    Transform(false);
    for (int32_t k = 0; k < num_bins_; ++k) {
      output[2 * k] = static_cast<float>(real_[k]);
      output[2 * k + 1] = static_cast<float>(imag_[k]);
    }
  }

  void Inverse(const float *input, float *output) const {
    if (!radix2_) {
      for (int32_t n = 0; n != n_fft_; ++n) {
        double sum = input[0];
        if (n_fft_ % 2 == 0) {
          sum += input[2 * (num_bins_ - 1)] * ((n & 1) ? -1.0 : 1.0);
        }
        const double *p_cos = cos_i_.data() + n * num_bins_;
        const double *p_sin = sin_i_.data() + n * num_bins_;
        for (int32_t k = 1; k != num_bins_ - 1; ++k) {
          double real = input[2 * k], imag = input[2 * k + 1];
          sum += 2.0 * (real * p_cos[k] - imag * p_sin[k]);
        }
        output[n] = static_cast<float>(sum / n_fft_);
      }
      return;
    }
    // Reconstruct the Hermitian spectrum. Upstream ignores imaginary DC and
    // Nyquist components, even if the model emits nonzero values there.
    real_[0] = input[0];
    imag_[0] = 0;
    real_[reverse_[n_fft_ / 2]] = input[n_fft_];
    imag_[reverse_[n_fft_ / 2]] = 0;
    for (int32_t k = 1; k < n_fft_ / 2; ++k) {
      real_[reverse_[k]] = input[2 * k];
      imag_[reverse_[k]] = input[2 * k + 1];
      real_[reverse_[n_fft_ - k]] = input[2 * k];
      imag_[reverse_[n_fft_ - k]] = -static_cast<double>(input[2 * k + 1]);
    }
    Transform(true);
    for (int32_t n = 0; n < n_fft_; ++n) {
      output[n] = static_cast<float>(real_[n] / n_fft_);
    }
  }

 private:
  void Transform(bool inverse) const {
    // Input is already bit-reversed. The bounds are size_t to avoid signed
    // overflow in the final stage for large (otherwise valid) power-of-two N.
    for (size_t width = 2; width <= static_cast<size_t>(n_fft_); width *= 2) {
      const size_t half = width / 2, stride = n_fft_ / width;
      for (size_t base = 0; base < static_cast<size_t>(n_fft_); base += width) {
        for (size_t j = 0; j < half; ++j) {
          const size_t even = base + j, odd = even + half;
          const double c = cos_f_[j * stride];
          const double s = inverse ? sin_f_[j * stride] : -sin_f_[j * stride];
          const double tr = c * real_[odd] - s * imag_[odd];
          const double ti = c * imag_[odd] + s * real_[odd];
          real_[odd] = real_[even] - tr;
          imag_[odd] = imag_[even] - ti;
          real_[even] += tr;
          imag_[even] += ti;
        }
      }
    }
  }

  int32_t n_fft_, num_bins_;
  bool radix2_;
  std::vector<double> cos_f_, sin_f_, cos_i_, sin_i_;
  std::vector<uint32_t> reverse_;
  mutable std::vector<double> real_, imag_;
};

}  // namespace sherpa_onnx
#endif  // CUEBELL_SHERPA_STREAMING_DFT_H_
