// Matrix multiplication experiment: C = A * B for square n x n matrices, plus matrix
// transposition B = A^T (the simpler cache-oblivious problem from Frigo et al.).
//
// Storage: one std::vector<double>, row by row ("row-major").
// Element (row, col) is stored at index row * n + col.
//   - moving along a row   -> next element in memory (cache friendly)
//   - moving down a column -> jump of n elements = n * 8 bytes (cache unfriendly)
//
// Nine versions of the same multiplication. They do the same arithmetic and differ only in
// the order of the memory accesses and in how the matrices are stored:
//                     row-major             column-major          tile-wise
//   plain loops       naive, row_wise       col_wise              -
//   cache-aware       tiled                 tiled_col_major       tiled_tile_wise
//   cache-oblivious   oblivious_row_major   oblivious_col_major   oblivious_tile_wise
//
//   naive     textbook loops (i, j, k): inner loop walks DOWN a column of B
//   row_wise  reordered loops (i, k, j): inner loop walks ALONG rows
//   tiled     row_wise, done in small square tiles that fit in the CPU cache
// The other layouts and the recursive (cache-oblivious) versions are explained above their functions.
//
// Three versions of out-of-place transposition (B[j,i] = A[i,j]), all row-major:
//   transpose_naive       two nested loops (reads a row of A, writes a column of B)
//   transpose_tiled       same copy, done in T x T tiles (cache-aware)
//   transpose_oblivious   recursive split of the largest side until the block is small
// Transposition is O(n^2), so it can be measured at sizes where multiplication is too slow.
//
// Multiplication with B stored transposed (professor case: row-major A × column-major B):
//   transposed_b        loops i,j,k; both A and B^T walk contiguously in k
//   tiled_transposed_b  the same, in T x T tiles (cache-aware)
// B is converted with the out-of-place transpose outside the timed region.
//
// Usage: matrix_multiplication <version> <n> [repetitions] [tile_size] [reference]
//   matrix_multiplication row_wise 512
//   matrix_multiplication tiled 1024 5 32
//   matrix_multiplication tiled 4096 3 64 row_wise
//   matrix_multiplication oblivious_tile_wise 1024 5 32
//   matrix_multiplication transpose_oblivious 8192 5 32
//
// reference: which version the result is checked against before timing.
//   Multiplication: naive (default); it takes minutes at n >= 2048, so use row_wise there.
//   Transposition:  transpose_naive (default and only choice; still cheap at large n).

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

// ---------------------------------------------------------------------------------------------
// Other storage layouts. Same matrix, different order in memory:
//   row-major    element (r, c) at r * n + c               (everything above)
//   column-major element (r, c) at c * n + r               (the mirror image)
//   tile-wise    the matrix is cut into T x T tiles; each tile is stored as one contiguous block
//                (row-major inside the tile), the tiles are stored one after another, row of
//                tiles by row of tiles. Needs n to be a multiple of T.
// The input is generated in row-major, converted to the layout before timing, and the result is
// converted back to row-major for the check. The conversions are O(n^2) and are not timed.
// ---------------------------------------------------------------------------------------------

Matrix to_col_major(const Matrix& src, int n) {
    Matrix out(src.size());
    for (int r = 0; r < n; ++r)
        for (int c = 0; c < n; ++c)
            out[static_cast<std::size_t>(c) * n + r] = src[static_cast<std::size_t>(r) * n + c];
    return out;
}

// Position of element (r, c) in the tile-wise layout.
inline std::size_t tile_index(int r, int c, int n, int tile) {
    const std::size_t tiles_per_row = static_cast<std::size_t>(n / tile);
    const std::size_t tile_number = static_cast<std::size_t>(r / tile) * tiles_per_row + c / tile;
    return tile_number * tile * tile + static_cast<std::size_t>(r % tile) * tile + c % tile;
}

Matrix to_tile_wise(const Matrix& src, int n, int tile) {
    Matrix out(src.size());
    for (int r = 0; r < n; ++r)
        for (int c = 0; c < n; ++c)
            out[tile_index(r, c, n, tile)] = src[static_cast<std::size_t>(r) * n + c];
    return out;
}

Matrix from_col_major(const Matrix& src, int n) { return to_col_major(src, n); }  // a transpose

Matrix from_tile_wise(const Matrix& src, int n, int tile) {
    Matrix out(src.size());
    for (int r = 0; r < n; ++r)
        for (int c = 0; c < n; ++c)
            out[static_cast<std::size_t>(r) * n + c] = src[tile_index(r, c, n, tile)];
    return out;
}

// Column-major mirror of row_wise: loop order j, k, i, so the inner loop walks down a column,
// which is contiguous in column-major storage.
void multiply_col_wise(const Matrix& A, const Matrix& B, Matrix& C, int n) {
    std::fill(C.begin(), C.end(), 0.0);

    for (int j = 0; j < n; ++j) {
        for (int k = 0; k < n; ++k) {
            const double b = B[static_cast<std::size_t>(j) * n + k];
            for (int i = 0; i < n; ++i) {
                C[static_cast<std::size_t>(j) * n + i] += A[static_cast<std::size_t>(k) * n + i] * b;
            }
        }
    }
}

// Cache-aware on the column-major layout: the mirror of multiply_tiled. The data is cut into
// tile x tile pieces and the inner loop (j, k, i) walks down a column, which is contiguous here.
// The tile is not contiguous in memory: its columns are n elements apart, like the rows of a
// tile in the row-major version.
void multiply_tiled_col_major(const Matrix& A, const Matrix& B, Matrix& C, int n, int tile) {
    std::fill(C.begin(), C.end(), 0.0);

    for (int jj = 0; jj < n; jj += tile) {
        const int j_end = std::min(jj + tile, n);
        for (int ii = 0; ii < n; ii += tile) {
            const int i_end = std::min(ii + tile, n);
            for (int kk = 0; kk < n; kk += tile) {
                const int k_end = std::min(kk + tile, n);

                for (int j = jj; j < j_end; ++j) {
                    for (int k = kk; k < k_end; ++k) {
                        const double b = B[static_cast<std::size_t>(j) * n + k];
                        for (int i = ii; i < i_end; ++i) {
                            C[static_cast<std::size_t>(j) * n + i] +=
                                A[static_cast<std::size_t>(k) * n + i] * b;
                        }
                    }
                }
            }
        }
    }
}

// Multiply one tile: C-tile += A-tile * B-tile. Each tile is T x T, contiguous, row-major.
void multiply_one_tile(const double* A, const double* B, double* C, int tile) {
    for (int i = 0; i < tile; ++i) {
        for (int k = 0; k < tile; ++k) {
            const double a = A[i * tile + k];
            for (int j = 0; j < tile; ++j) {
                C[i * tile + j] += a * B[k * tile + j];
            }
        }
    }
}

// Cache-aware on the tile-wise layout: the same three loops over tiles as multiply_tiled, but each
// tile is contiguous in memory. The tile size is chosen to fit the cache.
void multiply_tiled_tile_wise(const Matrix& A, const Matrix& B, Matrix& C, int n, int tile) {
    std::fill(C.begin(), C.end(), 0.0);

    const int tiles = n / tile;
    const std::size_t tile_elems = static_cast<std::size_t>(tile) * tile;
    for (int ti = 0; ti < tiles; ++ti) {
        for (int tj = 0; tj < tiles; ++tj) {
            for (int tk = 0; tk < tiles; ++tk) {
                multiply_one_tile(&A[(static_cast<std::size_t>(ti) * tiles + tk) * tile_elems],
                                  &B[(static_cast<std::size_t>(tk) * tiles + tj) * tile_elems],
                                  &C[(static_cast<std::size_t>(ti) * tiles + tj) * tile_elems],
                                  tile);
            }
        }
    }
}

// --- Cache-oblivious multiplication ---
// C += A * B is split recursively: the largest of the three dimensions (rows of C, columns of C,
// the shared dimension k) is cut in half and the two halves are done one after the other, until
// the block is small. The program never uses the cache size. Whatever the cache size is, at some
// depth of the recursion the blocks fit into it, and the data is reused there. The only limit is
// `base`, the block size at which the recursion stops and plain loops take over. It only
// controls the call overhead (it is not tuned to a cache).
//
// The k halves are done in order (first half, then second half), so every element of C is summed
// in the same order k = 0, 1, 2, ... as in the other versions and the checksums stay identical.

// Position of element (r, c) in a row-major or column-major matrix with leading dimension ld.
template <bool ColMajor>
inline std::size_t at(int r, int c, int ld) {
    return ColMajor ? static_cast<std::size_t>(c) * ld + r : static_cast<std::size_t>(r) * ld + c;
}

// Small block: C(mi x nj) += A(mi x pk) * B(pk x nj). The loop order is the one that walks
// contiguously through memory for the layout (i,k,j for row-major, j,k,i for column-major).
template <bool ColMajor>
void multiply_small_block(const double* A, const double* B, double* C, int ld, int mi, int pk, int nj) {
    if constexpr (ColMajor) {
        for (int j = 0; j < nj; ++j) {
            for (int k = 0; k < pk; ++k) {
                const double b = B[at<true>(k, j, ld)];
                for (int i = 0; i < mi; ++i) {
                    C[at<true>(i, j, ld)] += A[at<true>(i, k, ld)] * b;
                }
            }
        }
    } else {
        for (int i = 0; i < mi; ++i) {
            for (int k = 0; k < pk; ++k) {
                const double a = A[at<false>(i, k, ld)];
                for (int j = 0; j < nj; ++j) {
                    C[at<false>(i, j, ld)] += a * B[at<false>(k, j, ld)];
                }
            }
        }
    }
}

// A, B, C point to the top-left element of the current block of each matrix.
template <bool ColMajor>
void oblivious_recursive(const double* A, const double* B, double* C, int ld,
                         int mi, int pk, int nj, int base) {
    if (mi <= base && pk <= base && nj <= base) {
        multiply_small_block<ColMajor>(A, B, C, ld, mi, pk, nj);
    } else if (mi >= pk && mi >= nj) {  // split the rows of A and C
        const int half = mi / 2;
        oblivious_recursive<ColMajor>(A, B, C, ld, half, pk, nj, base);
        oblivious_recursive<ColMajor>(A + at<ColMajor>(half, 0, ld), B, C + at<ColMajor>(half, 0, ld),
                                      ld, mi - half, pk, nj, base);
    } else if (nj >= pk) {  // split the columns of B and C
        const int half = nj / 2;
        oblivious_recursive<ColMajor>(A, B, C, ld, mi, pk, half, base);
        oblivious_recursive<ColMajor>(A, B + at<ColMajor>(0, half, ld), C + at<ColMajor>(0, half, ld),
                                      ld, mi, pk, nj - half, base);
    } else {  // split the shared dimension: columns of A and rows of B
        const int half = pk / 2;
        oblivious_recursive<ColMajor>(A, B, C, ld, mi, half, nj, base);
        oblivious_recursive<ColMajor>(A + at<ColMajor>(0, half, ld), B + at<ColMajor>(half, 0, ld), C,
                                      ld, mi, pk - half, nj, base);
    }
}

template <bool ColMajor>
void multiply_oblivious(const Matrix& A, const Matrix& B, Matrix& C, int n, int base) {
    std::fill(C.begin(), C.end(), 0.0);
    oblivious_recursive<ColMajor>(A.data(), B.data(), C.data(), n, n, n, n, base);
}

// Cache-oblivious on the tile-wise layout. The recursion is over whole tiles (it stops at one
// tile, then multiply_one_tile runs). The recursion itself uses no cache size, but the layout does:
// the tile size T is fixed by the layout and has to be chosen.
// (ti, tj, tk) is the first tile of the block; mt, nt, pt are its size in tiles.
void oblivious_tiles_recursive(const Matrix& A, const Matrix& B, Matrix& C, int tiles, int tile,
                               int ti, int tj, int tk, int mt, int nt, int pt) {
    const std::size_t tile_elems = static_cast<std::size_t>(tile) * tile;
    if (mt == 1 && nt == 1 && pt == 1) {
        multiply_one_tile(&A[(static_cast<std::size_t>(ti) * tiles + tk) * tile_elems],
                          &B[(static_cast<std::size_t>(tk) * tiles + tj) * tile_elems],
                          &C[(static_cast<std::size_t>(ti) * tiles + tj) * tile_elems], tile);
    } else if (mt >= pt && mt >= nt) {
        const int half = mt / 2;
        oblivious_tiles_recursive(A, B, C, tiles, tile, ti, tj, tk, half, nt, pt);
        oblivious_tiles_recursive(A, B, C, tiles, tile, ti + half, tj, tk, mt - half, nt, pt);
    } else if (nt >= pt) {
        const int half = nt / 2;
        oblivious_tiles_recursive(A, B, C, tiles, tile, ti, tj, tk, mt, half, pt);
        oblivious_tiles_recursive(A, B, C, tiles, tile, ti, tj + half, tk, mt, nt - half, pt);
    } else {
        const int half = pt / 2;
        oblivious_tiles_recursive(A, B, C, tiles, tile, ti, tj, tk, mt, nt, half);
        oblivious_tiles_recursive(A, B, C, tiles, tile, ti, tj, tk + half, mt, nt, pt - half);
    }
}

void multiply_oblivious_tile_wise(const Matrix& A, const Matrix& B, Matrix& C, int n, int tile) {
    std::fill(C.begin(), C.end(), 0.0);
    const int tiles = n / tile;
    oblivious_tiles_recursive(A, B, C, tiles, tile, 0, 0, 0, tiles, tiles, tiles);
}

// --- Matrix transposition: B = A^T (out of place, both matrices row-major) ---
// The naive loops read along a row of A (contiguous) and write down a column of B (stride n).
// That write stream is the cache problem. Tiling and the recursive split keep a small block of
// B contiguous in the working set so the writes hit the cache.

void transpose_naive(const Matrix& A, Matrix& B, int n) {
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            B[static_cast<std::size_t>(j) * n + i] = A[static_cast<std::size_t>(i) * n + j];
        }
    }
}

void transpose_tiled(const Matrix& A, Matrix& B, int n, int tile) {
    for (int ii = 0; ii < n; ii += tile) {
        const int i_end = std::min(ii + tile, n);
        for (int jj = 0; jj < n; jj += tile) {
            const int j_end = std::min(jj + tile, n);
            for (int i = ii; i < i_end; ++i) {
                for (int j = jj; j < j_end; ++j) {
                    B[static_cast<std::size_t>(j) * n + i] = A[static_cast<std::size_t>(i) * n + j];
                }
            }
        }
    }
}

// Transpose the mi x nj block of A (top-left at A) into the nj x mi block of B (top-left at B).
// ld_a / ld_b are the leading dimensions of the full matrices. Recurse on the longer side until
// both sides are at most `base`, then copy with plain loops.
void transpose_oblivious_recursive(const double* A, double* B, int ld_a, int ld_b,
                                   int mi, int nj, int base) {
    if (mi <= base && nj <= base) {
        for (int i = 0; i < mi; ++i) {
            for (int j = 0; j < nj; ++j) {
                B[static_cast<std::size_t>(j) * ld_b + i] = A[static_cast<std::size_t>(i) * ld_a + j];
            }
        }
        return;
    }
    if (mi >= nj) {
        const int half = mi / 2;
        transpose_oblivious_recursive(A, B, ld_a, ld_b, half, nj, base);
        transpose_oblivious_recursive(A + static_cast<std::size_t>(half) * ld_a, B + half,
                                      ld_a, ld_b, mi - half, nj, base);
    } else {
        const int half = nj / 2;
        transpose_oblivious_recursive(A, B, ld_a, ld_b, mi, half, base);
        transpose_oblivious_recursive(A + half, B + static_cast<std::size_t>(half) * ld_b,
                                      ld_a, ld_b, mi, nj - half, base);
    }
}

void transpose_oblivious(const Matrix& A, Matrix& B, int n, int base) {
    transpose_oblivious_recursive(A.data(), B.data(), n, n, n, n, base);
}

// --- Multiplication with B stored as B^T (row-major A, transposed B) ---
// BT holds B^T in row-major, so BT[j * n + k] = B[k, j]. The textbook loops i,j,k then walk
// both A and BT contiguously in k (professor case "row-major times col-major"). This is the
// same arithmetic traffic as row_wise, but with the classic loop order and an explicit transpose
// of B (done outside the timed region). tiled_transposed_b adds cache-aware tiling on top.

void multiply_transposed_b(const Matrix& A, const Matrix& BT, Matrix& C, int n) {
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            double sum = 0.0;
            for (int k = 0; k < n; ++k) {
                sum += A[static_cast<std::size_t>(i) * n + k] *
                       BT[static_cast<std::size_t>(j) * n + k];
            }
            C[static_cast<std::size_t>(i) * n + j] = sum;
        }
    }
}

void multiply_tiled_transposed_b(const Matrix& A, const Matrix& BT, Matrix& C, int n, int tile) {
    std::fill(C.begin(), C.end(), 0.0);

    for (int ii = 0; ii < n; ii += tile) {
        const int i_end = std::min(ii + tile, n);
        for (int jj = 0; jj < n; jj += tile) {
            const int j_end = std::min(jj + tile, n);
            for (int kk = 0; kk < n; kk += tile) {
                const int k_end = std::min(kk + tile, n);

                for (int i = ii; i < i_end; ++i) {
                    for (int j = jj; j < j_end; ++j) {
                        double sum = C[static_cast<std::size_t>(i) * n + j];
                        for (int k = kk; k < k_end; ++k) {
                            sum += A[static_cast<std::size_t>(i) * n + k] *
                                   BT[static_cast<std::size_t>(j) * n + k];
                        }
                        C[static_cast<std::size_t>(i) * n + j] = sum;
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
    const bool is_transpose = algorithm.rfind("transpose_", 0) == 0;
    const std::string reference_name =
        argc > 5 ? argv[5] : (is_transpose ? "transpose_naive" : "naive");

    const bool known_multiply =
        algorithm == "naive" || algorithm == "row_wise" || algorithm == "tiled" ||
        algorithm == "col_wise" || algorithm == "tiled_col_major" ||
        algorithm == "tiled_tile_wise" || algorithm == "oblivious_row_major" ||
        algorithm == "oblivious_col_major" || algorithm == "oblivious_tile_wise" ||
        algorithm == "transposed_b" || algorithm == "tiled_transposed_b";
    const bool known_transpose = algorithm == "transpose_naive" || algorithm == "transpose_tiled" ||
                                 algorithm == "transpose_oblivious";
    const bool known_reference =
        is_transpose ? (reference_name == "transpose_naive")
                     : (reference_name == "naive" || reference_name == "row_wise");
    if ((!known_multiply && !known_transpose) || !known_reference || n < 1 || repetitions < 1 ||
        tile_size < 1) {
        std::cerr << "Usage: " << argv[0] << " <version> <n> [repetitions=7] [tile_size=32]"
                  << " [reference]\n"
                  << "  multiply:  naive row_wise tiled col_wise tiled_col_major tiled_tile_wise\n"
                  << "             oblivious_row_major oblivious_col_major oblivious_tile_wise\n"
                  << "             transposed_b tiled_transposed_b\n"
                  << "             reference = naive|row_wise (default naive)\n"
                  << "  transpose: transpose_naive transpose_tiled transpose_oblivious\n"
                  << "             reference = transpose_naive (default)\n"
                  << "  tile_size: tile / recursion base for tiled* and oblivious* versions\n";
        return 1;
    }

    // Random input, same seed every run.
    const std::size_t size = static_cast<std::size_t>(n) * n;
    std::mt19937_64 rng(12345);
    std::uniform_real_distribution<double> random_value(-1.0, 1.0);
    Matrix A(size), B(size), C(size), reference(size);
    for (double& x : A) x = random_value(rng);

    if (is_transpose) {
        // B holds A^T. Only A is filled; B starts unused and is written by the transpose.
        auto transpose = [&]() {
            if (algorithm == "transpose_naive") transpose_naive(A, B, n);
            else if (algorithm == "transpose_tiled") transpose_tiled(A, B, n, tile_size);
            else transpose_oblivious(A, B, n, tile_size);
        };

        transpose_naive(A, reference, n);
        transpose();
        for (std::size_t x = 0; x < size; ++x) {
            if (std::abs(B[x] - reference[x]) > 1e-9) {
                std::cerr << "Wrong result for " << algorithm << " at index " << x << "\n";
                return 1;
            }
        }

        const double ms = median_ms(transpose, repetitions);
        // Sixth CSV column is still named gflops for the shared scripts; for transpose it is
        // million elements copied per second (n^2 copies, no floating-point arithmetic).
        const double melems_per_s = static_cast<double>(n) * n / (ms * 1e3);
        const double checksum = std::accumulate(B.begin(), B.end(), 0.0);
        const bool uses_tile_size = algorithm != "transpose_naive";

        std::cout << "n,algorithm,tile_size,repetitions,median_ms,gflops,checksum\n"
                  << std::fixed << std::setprecision(6) << n << ',' << algorithm << ','
                  << (uses_tile_size ? tile_size : 0) << ',' << repetitions << ',' << ms << ','
                  << melems_per_s << ',' << checksum << '\n';
        return 0;
    }

    // --- Multiplication path ---
    for (double& x : B) x = random_value(rng);

    // Which storage layout the version uses.
    enum class Layout { RowMajor, ColMajor, TileWise, BTransposed };
    const Layout layout = (algorithm == "col_wise" || algorithm == "tiled_col_major" ||
                           algorithm == "oblivious_col_major")
                              ? Layout::ColMajor
                          : (algorithm == "tiled_tile_wise" || algorithm == "oblivious_tile_wise")
                              ? Layout::TileWise
                          : (algorithm == "transposed_b" || algorithm == "tiled_transposed_b")
                              ? Layout::BTransposed
                              : Layout::RowMajor;
    if (layout == Layout::TileWise && n % tile_size != 0) {
        std::cerr << algorithm << " needs n to be a multiple of the tile size (n=" << n
                  << ", tile_size=" << tile_size << ")\n";
        return 1;
    }

    // Versions with another layout work on converted copies (LA, LB, LC); the conversion is
    // outside the timed region. Row-major versions work on A, B, C directly.
    // BTransposed: only B is replaced by B^T (row-major of the transpose = column-major of B).
    Matrix LA, LB, LC;
    if (layout == Layout::ColMajor) {
        LA = to_col_major(A, n);
        LB = to_col_major(B, n);
        LC.assign(size, 0.0);
    } else if (layout == Layout::TileWise) {
        LA = to_tile_wise(A, n, tile_size);
        LB = to_tile_wise(B, n, tile_size);
        LC.assign(size, 0.0);
    } else if (layout == Layout::BTransposed) {
        LB = to_col_major(B, n);  // B^T in row-major order
    }

    auto multiply = [&]() {
        if (algorithm == "naive") multiply_naive(A, B, C, n);
        else if (algorithm == "row_wise") multiply_row_wise(A, B, C, n);
        else if (algorithm == "tiled") multiply_tiled(A, B, C, n, tile_size);
        else if (algorithm == "col_wise") multiply_col_wise(LA, LB, LC, n);
        else if (algorithm == "tiled_col_major") multiply_tiled_col_major(LA, LB, LC, n, tile_size);
        else if (algorithm == "tiled_tile_wise") multiply_tiled_tile_wise(LA, LB, LC, n, tile_size);
        else if (algorithm == "oblivious_row_major") multiply_oblivious<false>(A, B, C, n, tile_size);
        else if (algorithm == "oblivious_col_major") multiply_oblivious<true>(LA, LB, LC, n, tile_size);
        else if (algorithm == "oblivious_tile_wise") multiply_oblivious_tile_wise(LA, LB, LC, n, tile_size);
        else if (algorithm == "transposed_b") multiply_transposed_b(A, LB, C, n);
        else multiply_tiled_transposed_b(A, LB, C, n, tile_size);
    };

    // Check the answer against the reference version before timing anything.
    if (reference_name == "naive") multiply_naive(A, B, reference, n);
    else multiply_row_wise(A, B, reference, n);
    multiply();
    // The answer of a version with another layout is converted back to row-major.
    if (layout == Layout::ColMajor) C = from_col_major(LC, n);
    else if (layout == Layout::TileWise) C = from_tile_wise(LC, n, tile_size);
    for (std::size_t x = 0; x < size; ++x) {
        if (std::abs(C[x] - reference[x]) > 1e-9) {
            std::cerr << "Wrong result for " << algorithm << " at index " << x << "\n";
            return 1;
        }
    }

    const double ms = median_ms(multiply, repetitions);
    const double gflops = 2.0 * n * n * n / (ms * 1e6);  // n^3 multiply-adds
    const double checksum = std::accumulate(C.begin(), C.end(), 0.0);

    // tile_size is reported for the versions that use it, 0 for the others.
    const bool uses_tile_size =
        algorithm != "naive" && algorithm != "row_wise" && algorithm != "col_wise" &&
        algorithm != "transposed_b";

    std::cout << "n,algorithm,tile_size,repetitions,median_ms,gflops,checksum\n"
              << std::fixed << std::setprecision(6)
              << n << ',' << algorithm << ',' << (uses_tile_size ? tile_size : 0) << ','
              << repetitions << ',' << ms << ',' << gflops << ',' << checksum << '\n';
    return 0;
}
