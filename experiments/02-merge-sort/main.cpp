// Merge sort experiment: recursive (top-down) vs iterative (bottom-up).
//
// Both versions use the same iterative merge of two adjacent sorted runs, and the same
// pre-allocated temporary buffer. They differ only in the order of the merges:
//
//   recursive   split A into left/right halves, recurse, then merge the two sorted halves
//   iterative   outer loop over run width 1, 2, 4, ...; inner loop over adjacent blocks;
//               merge each pair of blocks (the unrolled recursion tree when |A| is a power of 2)
//
// The iterative version has no recursion overhead, but every outer pass walks the
// whole array (and may reload it into the cache).
// The recursive version, once a subarray fits in the cache, keeps working on that subarray until it is sorted.
//
// Usage: merge_sort <version> <n> [repetitions] [unused_tile=0] [reference=recursive]
//   merge_sort recursive 65536
//   merge_sort iterative 1048576 5
//
// n should be a power of 2 for the clean bottom-up picture (the code also accepts other n).
// The sixth CSV column is named gflops for the shared scripts; here it is million elements/s.

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <string>
#include <vector>

using Element = std::int64_t;
using Array = std::vector<Element>;

// Merge sorted A[lo, mid) and A[mid, hi) into A[lo, hi), using temp[lo, hi) as scratch.
void merge(Array &A, std::size_t lo, std::size_t mid, std::size_t hi, Array &temp)
{
    std::size_t i = lo;
    std::size_t j = mid;
    std::size_t k = lo;
    while (i < mid && j < hi)
    {
        if (A[i] <= A[j])
        {
            temp[k++] = A[i++];
        }
        else
        {
            temp[k++] = A[j++];
        }
    }
    while (i < mid)
    {
        temp[k++] = A[i++];
    }
    while (j < hi)
    {
        temp[k++] = A[j++];
    }
    for (std::size_t t = lo; t < hi; ++t)
    {
        A[t] = temp[t];
    }
}

// Merge Sort Recursive function
void mergesort_recursive(Array &A, std::size_t lo, std::size_t hi, Array &temp)
{
    if (hi - lo <= 1)
    {
        return;
    }
    const std::size_t mid = lo + (hi - lo) / 2;
    mergesort_recursive(A, lo, mid, temp);
    mergesort_recursive(A, mid, hi, temp);
    merge(A, lo, mid, hi, temp);
}

void mergesort_recursive(Array &A, Array &temp)
{
    mergesort_recursive(A, 0, A.size(), temp);
}

// Bottom-up mergesort: for width = 1, 2, 4, ..., merge adjacent blocks of that width.
void mergesort_iterative(Array &A, Array &temp)
{
    const std::size_t n = A.size();
    for (std::size_t width = 1; width < n; width *= 2)
    {
        for (std::size_t start = 0; start < n; start += 2 * width)
        {
            const std::size_t mid = std::min(start + width, n);
            const std::size_t end = std::min(start + 2 * width, n);
            if (mid < end)
            {
                merge(A, start, mid, end, temp);
            }
        }
    }
}

template <typename Work>
double median_ms(Work work, int repetitions)
{
    work();

    std::vector<double> times;
    times.reserve(static_cast<std::size_t>(repetitions));
    for (int r = 0; r < repetitions; ++r)
    {
        const auto start = std::chrono::steady_clock::now();
        work();
        const auto stop = std::chrono::steady_clock::now();
        times.push_back(std::chrono::duration<double, std::milli>(stop - start).count());
    }

    std::sort(times.begin(), times.end());
    return times[times.size() / 2];
}

bool is_power_of_two(std::size_t n)
{
    return n > 0 && (n & (n - 1)) == 0;
}

int main(int argc, char *argv[])
{
    const std::string algorithm = argc > 1 ? argv[1] : "";
    const int n_arg = argc > 2 ? std::atoi(argv[2]) : 0;
    const int repetitions = argc > 3 ? std::atoi(argv[3]) : 7;
    // argv[4] kept for script compatibility with matrix_multiplication (tile / unused).
    const std::string reference_name = argc > 5 ? argv[5] : "recursive";

    const bool known =
        algorithm == "recursive" || algorithm == "iterative";
    const bool known_reference =
        reference_name == "recursive" || reference_name == "iterative";
    if (!known || !known_reference || n_arg < 1 || repetitions < 1)
    {
        std::cerr << "Usage: " << argv[0]
                  << " <version> <n> [repetitions=7] [unused=0] [reference=recursive]\n"
                  << "  versions: recursive iterative\n"
                  << "  n: array length (prefer a power of 2)\n";
        return 1;
    }

    const std::size_t n = static_cast<std::size_t>(n_arg);
    if (!is_power_of_two(n))
    {
        std::cerr << "warning: n=" << n
                  << " is not a power of 2; iterative still works, but the "
                     "clean pass structure assumes powers of 2\n";
    }

    // Fixed seed so every version / session sees the same input and checksum.
    std::mt19937_64 rng(12345);
    std::uniform_int_distribution<Element> dist(
        std::numeric_limits<Element>::min() / 4,
        std::numeric_limits<Element>::max() / 4);

    Array original(n);
    for (Element &x : original)
    {
        x = dist(rng);
    }

    Array A = original;
    Array temp(n);
    Array reference = original;
    Array ref_temp(n);

    auto sort_with = [&](const std::string &name, Array &data, Array &scratch)
    {
        if (name == "recursive")
        {
            mergesort_recursive(data, scratch);
        }
        else
        {
            mergesort_iterative(data, scratch);
        }
    };

    // Correctness check against the reference version (outside the timed region).
    sort_with(reference_name, reference, ref_temp);
    if (!std::is_sorted(reference.begin(), reference.end()))
    {
        std::cerr << "Reference " << reference_name << " did not produce a sorted array\n";
        return 1;
    }

    sort_with(algorithm, A, temp);
    if (A != reference)
    {
        std::cerr << "Wrong result for " << algorithm << " (differs from " << reference_name
                  << ")\n";
        return 1;
    }

    // Timed region: restore the unsorted input, then sort. Temp contents do not matter.
    auto work = [&]()
    {
        A = original;
        sort_with(algorithm, A, temp);
    };

    const double ms = median_ms(work, repetitions);
    // Million elements sorted per second (column name gflops kept for shared scripts).
    const double melems_per_s = static_cast<double>(n) / (ms * 1e3);
    const double checksum = std::accumulate(
        A.begin(), A.end(), 0.0,
        [](double sum, Element x)
        { return sum + static_cast<double>(x); });

    std::cout << "n,algorithm,tile_size,repetitions,median_ms,gflops,checksum\n"
              << std::fixed << std::setprecision(6) << n << ',' << algorithm << ',' << 0 << ','
              << repetitions << ',' << ms << ',' << melems_per_s << ',' << checksum << '\n';
    return 0;
}
