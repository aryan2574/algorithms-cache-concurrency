# Cache memory: theory notes

Background for all experiments. The miss-count formulas for matrix multiplication, the lower bound and the three regimes are in the [experiment 01 report](../../experiments/01-matrix-multiplication/README.md#3-theory); this page explains the hardware those formulas are about.

Machine used in this project: AMD Ryzen 5 5500U (Zen 2 architecture), measured inside WSL2. Values marked "lscpu" or "perf" were checked on this laptop on 2026-11-01.

## 1. Why caches exist

The caches L1, L2 and L3 are levels of small, fast memory between the CPU and main memory (RAM). They keep recently and frequently used data close to the CPU, so it does not have to be fetched from RAM every time.

A CPU core can execute instructions much faster than data arrives from main memory. Waiting for memory then becomes the bottleneck. This is called the "memory wall". The solution is a hierarchy of faster but smaller memories close to the CPU: the CPU caches.

## 2. The memory hierarchy

```text
        CPU core
           |
       Registers
           |
       L1 cache        split into L1 data + L1 instruction, private to each core
           |
       L2 cache        private to each core (on our CPU)
           |
       L3 cache        shared by a group of cores
           |
     Main memory (RAM)
           |
       SSD / HDD
```

Going down the hierarchy: bigger, slower, cheaper per byte.

Our laptop. Size, ways and sets come from `lscpu -C`. Latencies are typical published values for Zen 2 (AMD optimisation guide and public measurements), **not** measured on this laptop. At about 4 GHz, 1 cycle = 0.25 ns.

| Level | Size | Ways | Sets | Line | Latency (approx.) |
| --- | --- | ---: | ---: | ---: | --- |
| Registers | under 1 KB that a program can name (section 16) | - | - | - | 0 (inside the core) |
| L1 data | 32 KiB per core | 8 | 64 | 64 B | ~4-5 cycles (~1 ns) |
| L1 instruction | 32 KiB per core | 8 | 64 | 64 B | |
| L2 | 512 KiB per core | 8 | 1024 | 64 B | ~12 cycles (~3 ns) |
| L3 | 4 MiB per group of 3 cores (8 MiB on the chip = 2 x 4 MiB) | 16 | 4096 | 64 B | ~40 cycles (~10 ns) |
| RAM | gigabytes | - | - | - | ~90-130 ns (~400 cycles) |

- One core can only use the L3 of its own group of cores (AMD calls the group a CCX). For our single-threaded programs the usable L3 is therefore 4 MiB. WSL2 also reports "L3 4 MiB".
- Our CPU has no L4 cache.
- The CPU has 6 cores / 12 threads, but the WSL2 virtual machine sees only 4 logical CPUs (2 cores x 2 threads). This matters for future multithreading experiments.

## 3. The cache levels

**L1 cache:** closest to the CPU core. It is divided into two separate caches:

- L1 instruction cache: stores the instructions the CPU is about to execute.
- L1 data cache: stores the data the CPU reads and writes.

They are separated because instructions and data have different access patterns, and two caches can be accessed at the same time (fetch the next instruction while loading data).

| Property | L1 | L2 | L3 |
| --- | --- | --- | --- |
| Capacity | tens of KB (ours: 32 KiB data + 32 KiB instructions per core) | hundreds of KB to several MB (ours: 512 KiB per core) | several MB to tens of MB (ours: 4 MiB per group of 3 cores) |
| Speed | fastest (~4-5 cycles) | slower than L1 (~12 cycles) | slower than L1 and L2 (~40 cycles) |
| Location | inside each core | usually private to a core (ours is) | shared by some or all cores |
| Organisation | split into instruction and data caches | usually unified | unified |
| Purpose | instructions and data needed right now | a larger working set close to the core | a larger working set; fewer RAM accesses |

Some architectures have a separate L2 for each core, others share an L2 between a group of cores. On our CPU the L2 is inclusive of the L1: everything in L1 is also in L2.

Why L3? Two cores running different threads may use some of the same data. A shared last-level cache lets both cores benefit from one large cache instead of every core needing its own large cache. The last cache before RAM is called the Last Level Cache (LLC). On our CPU that is the L3.

Special feature of our L3: it is a **victim cache**. Lines coming from RAM go into L2 and L1, not into L3. A line enters the L3 only when it is evicted from an L2. So L2 and L3 hold mostly different data, and one core can keep about 512 KiB + 4 MiB = 4.5 MiB close by.

## 4. Cache lines, hits and misses

The CPU moves data between the levels in blocks called cache lines. Most modern x86 processors, including ours, use 64-byte lines. A 64-byte line holds 8 values of type `double`.

- **Cache hit:** the requested data is already in the cache.
- **Cache miss:** the requested data is not in the cache, so the processor must get it from a lower level of the memory hierarchy.

On a miss, the whole 64-byte line is copied in, not just the requested bytes. Reading the neighbouring values afterwards is then free. This is why walking along a row of a matrix (neighbours in memory) is much cheaper than walking down a column.

## 5. How the CPU looks up data

For `int x = arr[10];` the processor generates a memory request for the address of `arr[10]`:

1. L1 lookup: is the cache line containing this address present? Hit: return the data. Miss: check L2.
2. L2 lookup. Hit: return the data (and copy the line into L1). Miss: check L3.
3. L3 lookup. Hit: return the data (and copy the line into L2 and L1). Miss: access RAM.
4. RAM: fetch the line (it goes into L2 and L1; on our CPU not into L3).

In reality these steps overlap. An out-of-order core keeps executing other instructions while a miss is being served, and it can have many misses in flight at the same time.

## 6. How data is organised inside a cache: sets, ways, tags

A cache is divided into **sets**, and each set has a fixed number of slots called **ways**. Our L1 data cache: 64 sets x 8 ways = 512 lines; 512 lines x 64 B = 32 KiB.

The cache uses the memory address to find the right place. The address is split into:

```text
    ┌───────────────┬─────────────┬──────────────┐
    │      TAG      │  SET INDEX  │ BYTE OFFSET  │
    │   bits 12+    │  bits 6-11  │  bits 0-5    │   <- for our L1
    └───────────────┴─────────────┴──────────────┘
```

- Byte offset: which byte inside the 64-byte line (64 = 2^6, so 6 bits).
- Set index: which set to search (64 sets = 2^6, so 6 bits).
- Tag: which memory block is stored in a line of that set.

The cache uses the set index to find the set, then compares the tag of the request with the tags of the 8 ways in that set. A valid matching tag is a hit. In one formula, for our L1: `set = (address / 64) mod 64`.

**Important for the experiments:** two addresses that are a multiple of 64 x 64 = 4096 bytes apart always have the same set index, so they compete for the same 8 ways.

Example: one row of a 512 x 512 matrix of doubles is 512 x 8 = 4096 bytes. So `B[0][j]`, `B[1][j]`, `B[2][j]`, ... (one column) all map to the **same** L1 set. Walking down a column, only 8 lines of that column can be in L1 at the same time, although L1 has 512 lines. The same is true for n = 1024 (8192-byte rows). For n = 256 the column uses 2 sets, for n = 128 4 sets. For n = 1000 a row is 8000 bytes = 125 lines, so the next row lands 61 sets further on (125 mod 64 = 61) and a column spreads over all 64 sets. Powers of two are the worst case for set-associative caches.

Alignment on this machine (checked 2026-11-01): glibc puts the four `std::vector` buffers at page + 16 bytes for every n >= 250 (`address % 64 = 16` and `address % 4096 = 16`). A full row then occupies n/L + 1 lines, not n/L. A 32-double tile row that starts mid-line spans 5 lines rather than 4 (about +25% traffic for `tiled`, +1-3% for `row_wise`).

L2 (1024 sets, index bits 6-15) and L3 (4096 sets, index bits 6-17) use the physical address. Address bits 12 and above depend on which physical page the operating system picked (pages are 4 KiB), so for steps of 4 KiB or more the L2/L3 placement is partly random. For a column with a 4096-byte step, bits 6-11 stay the same, so the column can use only 16 of the 1024 L2 sets (16 x 8 = 128 lines) and 64 of the 4096 L3 sets (64 x 16 = 1024 lines). L1 placement is exactly predictable: its index bits 6-11 lie inside the 4 KiB page offset, which is the same in the virtual and the physical address. (This is also why L1 is 32 KiB with 8 ways: 32 KiB / 8 = 4 KiB = one page.)

## 7. Associativity

| Organisation | Where can a block go? |
| --- | --- |
| Direct-mapped | exactly one cache location |
| Set-associative | any way within its assigned set |
| Fully associative | any cache location |

Our caches: L1 and L2 are 8-way, L3 is 16-way set-associative. More ways means fewer conflict misses, but more tags to compare on each access (more time and power). The ideal-cache model (section 18) assumes a fully associative cache.

## 8. How caches work: locality

1. **Temporal locality:** data used once is likely to be used again soon, so it makes sense to keep it in the cache rather than fetch it over and over. Example: `row_wise` updates the same row of C n times; `tiled` reuses each loaded tile d times.
2. **Spatial locality:** after accessing one memory location, nearby locations are likely to be accessed soon, for example array elements read one after another. One fetched cache line also brings the neighbouring elements. Example: `row_wise` reads B and C along rows and uses all 8 doubles of every line it loads; `naive` walks down columns of B and uses only 1 double of each line it loads.

## 9. Replacement policies

When the cache (or one set) is full, an existing line must be removed to make room. Common policies:

1. LRU (Least Recently Used): replace the line that has not been used for the longest time.
2. FIFO (First In, First Out): replace the line that entered first.
3. Pseudo-LRU: an approximation of LRU that needs less hardware. Real CPUs use variants of this; AMD does not publish the exact policy.

A weakness of LRU: if a loop cycles through more lines than fit (in the cache, or in one set), LRU evicts every line just before it is needed again, so **every** access misses. On a single cache with a sharp capacity limit that looks like a cliff. On this machine the L3 drop for `row_wise` is gradual: GFLOPS stay around 5-6.5 up to n = 512 (B = 2 MiB), start falling from about n = 600 (B = 2.9 MiB), and reach 2.6 at n = 1000 (B = 7.6 MiB). The textbook size n = sqrt(4 MiB / 8) = 724 is therefore only a landmark, not a step. The usable L3 is smaller than 4 MiB (victim cache, shared with other cores, A and C also pass through it).

The theory uses "optimal replacement" (evict the line that is needed furthest in the future, Belady's algorithm). Hardware cannot do this, but it gives clean formulas, and for our access patterns LRU gives the same counts except close to the regime boundaries.

## 10. Types of cache misses (the "three Cs")

1. **Compulsory miss:** the first access to a memory block. For C = A x B with n x n matrices: at least 3n²/L lines (read A and B once, write C once).
2. **Capacity miss:** the cache cannot hold the working set. `row_wise` at n = 512: B (2 MiB) does not fit in L1 (32 KiB), so B is loaded again for every row i: about n³/L L1 misses.
3. **Conflict miss:** there is enough space in total, but too many lines map to the same set. `tiled` at n = 512: the 32 rows of a tile map to the same few L1 sets (4096-byte rows, section 6), which have only 8 ways each, so the tile does not stay in L1.

## 11. Writes

- Write-back: a store changes the line in the cache. The line is written to the next level only when it is evicted. A changed line is called "dirty".
- Write-allocate: a store to a line that is not in the cache first loads that line.
- In matrix multiplication C is written. Its lines are loaded like other lines and written back about once: around n²/L extra transfers, small next to n³/L. (Exception: if the row of C cannot stay in the cache, it is loaded and written back again and again.)

## 12. Hardware prefetching

- The L1 and L2 caches have prefetchers. They watch the addresses of misses, detect sequential or fixed-step patterns, and load lines before the program asks for them.
- Prefetching hides waiting time, but it does **not** reduce the number of lines moved. The theory counts lines moved, so a counter that includes prefetched lines matches the theory better. Our L1 counter (`L1-dcache-load-misses`) includes them; our L2 counter (`cache-misses`) does not (section 17).
- Prefetchers usually stop at a 4 KiB page boundary. `naive` at n = 512 or more jumps to a new page on every access to B, so it gets no help. `row_wise` reads B sequentially, so the L2 prefetcher loads most lines in advance and few L2 misses are left for the counter to see.

## 13. Virtual memory, pages and the TLB

- Programs use virtual addresses. The hardware translates them to physical addresses page by page. Pages are 4 KiB on our system (`getconf PAGESIZE`). Transparent huge pages are set to "madvise", so our `std::vector` matrices use normal 4 KiB pages.
- The TLB (translation lookaside buffer) is a cache for these translations. Zen 2 has an L1 data TLB with 64 entries and an L2 TLB with 2048 entries. A miss in both needs a page-table walk (extra memory accesses).
- 64 entries x 4 KiB = 256 KiB of data reachable without an L1 TLB miss; 2048 entries x 4 KiB = 8 MiB with the L2 TLB.
- `naive` at n = 512: each step down a column of B is 4096 bytes, a new page. One column touches 512 pages, more than the 64-entry L1 TLB, so almost every access to B misses the L1 TLB (~n³ L1-TLB misses measured). Three matrices are 1536 pages, which still fit in the 2048-entry L2 TLB, so page walks stay around 1.2 M, not hundreds of millions.
- `naive` at n = 1024: B alone is 2048 pages and A+B+C are 6144 pages, more than the L2 TLB. Measured page walks: 114 M. That is a second reason n = 1024 `naive` is much slower than n = 1000 (3.2 M walks), on top of the L1/L2 conflict misses.
- `row_wise` and `tiled` walk pages in order, so the same TLB entry is reused for 512 consecutive doubles. L1-TLB misses stay in the low millions even at n = 1024.

## 14. Latency, bandwidth and AMAT

- **Latency:** how long one access takes (for example ~100 ns for RAM).
- **Bandwidth:** how many bytes per second can be moved (for example ~10-20 GB/s from RAM for one core).

Sequential access (`row_wise`) is limited by bandwidth: the prefetchers keep many requests in flight. Access without prefetching (`naive`'s column walk) is limited by latency.

Average Memory Access Time:

```text
AMAT = T_L1 + MR_L1 x (T_L2 + MR_L2 x (T_L3 + MR_L3 x P_RAM))
```

| Symbol | Meaning |
| --- | --- |
| T_L1 | time to access L1 |
| T_L2 | time to access L2 after an L1 miss |
| T_L3 | time to access L3 after an L2 miss |
| MR_L1, MR_L2, MR_L3 | local miss rate of each level (misses / accesses at this level) |
| P_RAM | additional penalty to access RAM after an L3 miss |

Even with a large L3, a high L1 hit rate is extremely valuable. Rough example with our n = 512 measurements (T_L1 = 4, T_L2 = 12, T_L3 = 40 cycles; B fits in L3 at n = 512, so MR_L3 is close to 0):

- `naive`: MR_L1 = 65%, MR_L2 = 98%, so AMAT = 4 + 0.65 x (12 + 0.98 x 40) = about 37 cycles.
- `row_wise`: MR_L1 = 8.5%, MR_L2 = 3%, so AMAT = 4 + 0.085 x (12 + 0.03 x 40) = about 5 cycles.

This is a simplification: out-of-order execution and prefetching overlap many accesses, so real programs are not simply "accesses x AMAT". But it shows why `naive` is so much slower.

Example of a bandwidth limit: `row_wise` at n = 1024. B (8 MiB) does not fit in L3, so it is read from RAM once for every row i: n³/L lines x 64 B = 8.6 GB per multiplication. At the 2026-10-18 time of 742 ms that is about 11.6 GB/s; at the 2026-11-01 time of 788 ms it is about 10.9 GB/s. Both are a normal rate for one core reading from RAM.

## 15. Cost per byte

The lower we go in the memory hierarchy, the cheaper it is to store each byte.

| Memory | Relative cost per byte | Speed |
| --- | --- | --- |
| CPU registers | very high | extremely fast |
| L1 cache | very high | extremely fast |
| L2 cache | high | very fast |
| L3 cache | lower | fast |
| RAM | much lower | slower |
| SSD | even lower | much slower |

This is because the memory technologies cost different amounts to manufacture:

- CPU caches (SRAM): very fast, but need relatively much chip area per bit, so they are expensive.
- RAM (DRAM): slower, but offers much more capacity at a lower cost per bit.
- SSD (flash memory): much more capacity at an even lower cost per byte, but with much higher access latency.

## 16. CPU core

A CPU core is an independent processing unit inside a processor that can execute program instructions: each core executes instructions, performs calculations and processes data.

| Component | Purpose |
| --- | --- |
| Control unit | coordinates instruction execution |
| ALU | integer arithmetic and logical operations |
| FPU / SIMD units | floating-point calculations, several numbers per instruction |
| Registers | hold the few values the current instructions work on |
| L1 cache | data and instructions in use right now (~1 ns away) |
| L2 cache | additional fast storage for instructions and data (~3 ns away) |

Modern cores also contain instruction pipelines, branch predictors, load/store units and other execution resources.

Registers: x86-64 has 16 general-purpose registers of 8 bytes and, with AVX2, 16 vector registers of 32 bytes, under 1 KB that a program can name. (Internally the core has many more physical registers, used for register renaming.)

SIMD (single instruction, multiple data): one instruction works on several numbers at once.

- SSE2: 128-bit registers = 2 doubles per instruction (every x86-64 CPU has it).
- AVX2: 256-bit registers = 4 doubles per instruction (our CPU has it, plus FMA).

Our Release build uses `-O3` without `-march=native`, so the compiler may only use SSE2. Checked with `objdump` on 2026-11-01: the program uses 128-bit `xmm` registers and `mulpd`, and no 256-bit `ymm` registers and no FMA instructions. The vectorisation effect in experiment 01 is therefore an SSE2 (2-wide) effect.

## 17. Measuring caches on this machine (perf)

perf's generic event names are mapped to different hardware events on different CPUs. On Intel, `cache-misses` means last-level-cache misses. **On our AMD Zen 2 it means L2 misses.** The table was checked on 2026-11-01 by counting each generic name together with the AMD raw event code in the same run (equal counts; see `experiments/01-matrix-multiplication/results/2026-11-01-ryzen5500u-wsl2/perf-event-mapping.txt`).

| perf name | AMD raw code | What it counts on our CPU |
| --- | --- | --- |
| `L1-dcache-loads` | `r0040` | L1 data cache accesses, loads **and** stores, one per instruction (one SSE2 instruction moves 2 doubles) |
| `L1-dcache-load-misses` | `rc860` | requests from the L1 data cache to L2: read misses, L1 prefetches, store misses. About "lines brought into L1" |
| `cache-references` | `rff60` | all requests to L2 |
| `cache-misses` | `r0964` | L2 misses of data reads and instruction fetches; lines brought in by the L2 prefetcher are not included |
| `dTLB-loads` | `rff45` | L1 data TLB misses (lookups in the L2 TLB) |
| `dTLB-load-misses` | `rf045` | L2 TLB misses (page-table walks) |

Not available in WSL2: L3 and memory-controller counters (Linux shows no `amd_l3` or `amd_df` device under `/sys/bus/event_source/devices`). L3 and RAM traffic must therefore be inferred from timings, or measured on native Linux.

## 18. The cache model used for the theory

Ideal-cache model (Frigo et al., 1999): one cache of Z elements with lines of L elements, fully associative, optimal replacement. We count lines moved into the cache = cache misses Q. Our L1: Z = 4096 doubles (32 KiB), L = 8 doubles (64 B). L2: Z = 65536. L3: Z = 524288.

Results for C = A x B with n x n matrices (derivations in the [experiment 01 report](../../experiments/01-matrix-multiplication/README.md#3-theory)):

| Version | Misses Q | Condition |
| --- | --- | --- |
| `naive` | n³ | the cache holds fewer than about n lines (or the column conflicts in a few sets) |
| `naive` | n³/L | it holds n lines but not the whole matrix B |
| `row_wise` | n³/L | B is read again for every row of A |
| `tiled` | 2n³/(dL) + n²/L | d x d tiles, if three tiles fit (3d² <= Z) |
| any algorithm doing the n³ multiply-adds | >= 2n³/(L sqrt(Z)) | lower bound (Hong and Kung 1981; constant: Smith et al. 2017) |
| any algorithm | >= 3n²/L | every input read once, every output written once |

If the whole problem fits in the cache, every version has only the 3n²/L compulsory misses.

Real caches differ from the model: set associativity (conflict misses), pseudo-LRU instead of optimal replacement, prefetching, several cache levels, and the TLB. The experiment 01 report shows where these differences matter in our measurements.

## 19. References

- AMD: Software Optimization Guide for AMD Family 17h Models 30h and Greater Processors (Zen 2): cache and TLB sizes and latencies.
- AMD: Processor Programming Reference (PPR) for Family 17h processors: performance counter events PMCx040, PMCx045, PMCx060, PMCx064.
- Linux kernel source, `arch/x86/events/amd/core.c`: which hardware event each generic perf event name uses on AMD.
- U. Drepper: What Every Programmer Should Know About Memory, 2007.
- J. Hennessy, D. Patterson: Computer Architecture: A Quantitative Approach, chapter on the memory hierarchy (three Cs, AMAT).
- M. Frigo, C. Leiserson, H. Prokop, S. Ramachandran: Cache-Oblivious Algorithms, FOCS 1999.
- J.-W. Hong, H. T. Kung: I/O Complexity: The Red-Blue Pebble Game, STOC 1981.
- T. M. Smith, B. Lowery, J. Langou, R. A. van de Geijn: A Tight I/O Lower Bound for Matrix Multiplication, arXiv:1702.02017, 2017.
- M. Lam, E. Rothberg, M. Wolf: The Cache Performance and Optimizations of Blocked Algorithms, ASPLOS 1991.
