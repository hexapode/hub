"""Reference baseline solution for fast integer sort."""

from __future__ import annotations


def sort_integers(data: list[int]) -> list[int]:
    """Pure-Python chunked merge sort baseline."""
    arr = list(data)
    n = len(arr)
    if n <= 1:
        return arr

    # Sort small chunks of size 64 with insertion sort, then merge
    chunk = 64
    for start in range(0, n, chunk):
        end = min(start + chunk, n)
        for i in range(start + 1, end):
            key = arr[i]
            j = i - 1
            while j >= start and arr[j] > key:
                arr[j + 1] = arr[j]
                j -= 1
            arr[j + 1] = key

    width = chunk
    buf = [0] * n
    while width < n:
        for left in range(0, n, 2 * width):
            mid = min(left + width, n)
            right = min(left + 2 * width, n)
            i, j, k = left, mid, left
            while i < mid and j < right:
                if arr[i] <= arr[j]:
                    buf[k] = arr[i]
                    i += 1
                else:
                    buf[k] = arr[j]
                    j += 1
                k += 1
            while i < mid:
                buf[k] = arr[i]
                i += 1
                k += 1
            while j < right:
                buf[k] = arr[j]
                j += 1
                k += 1
        arr, buf = buf, arr
        width *= 2

    return arr
