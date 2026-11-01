// Matrix multiplication experiment: C = A * B for square n x n matrices.
//
// Storage: one std::vector<double>, row by row ("row-major").
// Element (row, col) is stored at index row * n + col.
//   - moving along a row   -> next element in memory (cache friendly)
//   - moving down a column -> jump of n elements = n * 8 bytes (cache unfriendly)
//
// Three versions of the same multiplication (they differ only in memory access):
//   naive     textbook loops (i, j, k): inner loop walks DOWN a column of B
//   row_wise  reordered loops (i, k, j): inner loop walks ALONG rows
//   tiled     row_wise, done in small square tiles that fit in the CPU cache
//
// Usage: matrix_multiplication <naive|row_wise|tiled> <n> [repetitions] [tile_size]
//   matrix_multiplication row_wise 512
//   matrix_multiplication tiled 1024 5 32

#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <string>
#include <vector>

using Matrix = std::vector<double>;

// Loop order i, j, k. B[k * n + j] changes k in the inner loop,
// so it walks down a column of B. Slow.
void multiply_naive(const Matrix& A, const Matrix& B, Matrix& C, int n) {
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            double sum = 0.0;
            for (int k = 0; k < n; ++k) {
                sum += A[i * n + k] * B[k * n + j];
            }
            C[i * n + j] = sum;
        }
    }
}

// Loop order i, k, j. B[k * n + j] changes j in the inner loop,
// so it walks along a row of B (and of C). Fast.
void multiply_row_wise(const Matrix& A, const Matrix& B, Matrix& C, int n) {
    std::fill(C.begin(), C.end(), 0.0);

    for (int i = 0; i < n; ++i) {
        for (int k = 0; k < n; ++k) {
            const double a = A[i * n + k];
            for (int j = 0; j < n; ++j) {
                C[i * n + j] += a * B[k * n + j];
            }
        }
    }
}

// Same as row_wise, but one tile (tile x tile piece) at a time,
// so the data being worked on stays in the CPU cache.
void multiply_tiled(const Matrix& A, const Matrix& B, Matrix& C, int n, int tile) {
    std::fill(C.begin(), C.end(), 0.0);

    for (int ii = 0; ii < n; ii += tile) {
        const int i_end = std::min(ii + tile, n);
        for (int jj = 0; jj < n; jj += tile) {
            const int j_end = std::min(jj + tile, n);
            for (int kk = 0; kk < n; kk += tile) {
                const int k_end = std::min(kk + tile, n);

                for (int i = ii; i < i_end; ++i) {
                    for (int k = kk; k < k_end; ++k) {
                        const double a = A[i * n + k];
                        for (int j = jj; j < j_end; ++j) {
                            C[i * n + j] += a * B[k * n + j];
                        }
                    }
                }
            }
        }
    }
}

// Run `work` once to warm up, then `repetitions` times. Returns the median in ms.
template <typename Work>
double median_ms(Work work, int repetitions) {
    work();

    std::vector<double> times;
    for (int r = 0; r < repetitions; ++r) {
        const auto start = std::chrono::steady_clock::now();
        work();
        const auto stop = std::chrono::steady_clock::now();
        times.push_back(std::chrono::duration<double, std::milli>(stop - start).count());
    }

    std::sort(times.begin(), times.end());
    return times[times.size() / 2];
}

int main(int argc, char* argv[]) {
    const std::string algorithm = argc > 1 ? argv[1] : "";
    const int n = argc > 2 ? std::atoi(argv[2]) : 0;
    const int repetitions = argc > 3 ? std::atoi(argv[3]) : 7;
    const int tile_size = argc > 4 ? std::atoi(argv[4]) : 32;

    const bool known = algorithm == "naive" || algorithm == "row_wise" || algorithm == "tiled";
    if (!known || n < 1 || repetitions < 1 || tile_size < 1) {
        std::cerr << "Usage: " << argv[0]
                  << " <naive|row_wise|tiled> <n> [repetitions=7] [tile_size=32]\n";
        return 1;
    }

    // Random input, same seed every run.
    const std::size_t size = static_cast<std::size_t>(n) * n;
    std::mt19937_64 rng(12345);
    std::uniform_real_distribution<double> random_value(-1.0, 1.0);
    Matrix A(size), B(size), C(size), reference(size);
    for (double& x : A) x = random_value(rng);
    for (double& x : B) x = random_value(rng);

    auto multiply = [&]() {
        if (algorithm == "naive") multiply_naive(A, B, C, n);
        else if (algorithm == "row_wise") multiply_row_wise(A, B, C, n);
        else multiply_tiled(A, B, C, n, tile_size);
    };

    // Check the answer against the naive version before timing anything.
    multiply_naive(A, B, reference, n);
    multiply();
    for (std::size_t x = 0; x < size; ++x) {
        if (std::abs(C[x] - reference[x]) > 1e-9) {
            std::cerr << "Wrong result for " << algorithm << " at index " << x << "\n";
            return 1;
        }
    }

    const double ms = median_ms(multiply, repetitions);
    const double gflops = 2.0 * n * n * n / (ms * 1e6);  // n^3 multiply-adds
    const double checksum = std::accumulate(C.begin(), C.end(), 0.0);

    std::cout << "n,algorithm,tile_size,repetitions,median_ms,gflops,checksum\n"
              << std::fixed << std::setprecision(6)
              << n << ',' << algorithm << ',' << (algorithm == "tiled" ? tile_size : 0) << ','
              << repetitions << ',' << ms << ',' << gflops << ',' << checksum << '\n';
    return 0;
}
