"""核心审计逻辑：环检测、区间传播收紧、字典序最小拓扑序。

约定：
- 年代为整数（百万年），数值越大越古老。
- 每条关系 (older, younger) 转为约束 age(older) >= age(younger) + 1，
  即有向边 older -> younger（由古老指向年轻）。
"""
from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class CycleFound:
    """关系图中存在环；path 为一条成环的编号路径，首尾相同。"""

    path: list[str]


@dataclass(frozen=True)
class ConflictFound:
    """传播后若干地层区间被压空；emptied 为 (编号, 下界, 上界)，下界 > 上界。"""

    emptied: list[tuple[str, int, int]]


@dataclass(frozen=True)
class Solved:
    """可行：intervals 为收紧后的 (下界, 上界)，order 为字典序最小的合法顺序。"""

    intervals: dict[str, tuple[int, int]]
    order: list[str]


def _build_adj(ids: list[str], edges: list[tuple[str, str]]) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {i: [] for i in ids}
    for older, younger in edges:
        adj[older].append(younger)
    return adj


def find_cycle_path(ids: list[str], edges: list[tuple[str, str]]) -> list[str] | None:
    """若关系图有环，返回一条成环路径（如 ["A", "B", "C", "A"]），否则返回 None。

    迭代式三色 DFS，避免深图触发递归上限。
    """
    adj = _build_adj(ids, edges)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(ids, WHITE)

    for root in ids:
        if color[root] != WHITE:
            continue
        color[root] = GRAY
        stack = [(root, iter(adj[root]))]
        path = [root]
        while stack:
            node, it = stack[-1]
            descended = False
            for nxt in it:
                if color[nxt] == WHITE:
                    color[nxt] = GRAY
                    stack.append((nxt, iter(adj[nxt])))
                    path.append(nxt)
                    descended = True
                    break
                if color[nxt] == GRAY:
                    # nxt 在当前 DFS 栈上，path 中从 nxt 到栈顶即构成环
                    return path[path.index(nxt):] + [nxt]
            if not descended:
                color[node] = BLACK
                stack.pop()
                path.pop()
    return None


def _topo_order(ids: list[str], adj: dict[str, list[str]]) -> list[str]:
    indeg = {i: 0 for i in ids}
    for older in ids:
        for younger in adj[older]:
            indeg[younger] += 1
    queue = deque(i for i in ids if indeg[i] == 0)
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in adj[node]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    return order


def tighten_intervals(
    ids: list[str],
    lower: dict[str, int],
    upper: dict[str, int],
    edges: list[tuple[str, str]],
) -> tuple[dict[str, int], dict[str, int]]:
    """沿关系图（须无环）传播，返回收紧后的 (下界, 上界)。

    - 上界沿 古老->年轻 方向下压：ub(younger) <= ub(older) - 1
    - 下界沿 年轻->古老 方向上抬：lb(older)   >= lb(younger) + 1
    在 DAG 上按拓扑序 / 逆拓扑序各扫一遍即达不动点。
    """
    adj = _build_adj(ids, edges)
    topo = _topo_order(ids, adj)
    if len(topo) != len(ids):
        raise ValueError("关系图存在环，请先调用 find_cycle_path")

    ub = dict(upper)
    lb = dict(lower)
    for node in topo:  # 处理到 node 时其所有前驱已处理完毕，ub(node) 已最终
        for nxt in adj[node]:
            if ub[nxt] > ub[node] - 1:
                ub[nxt] = ub[node] - 1
    for node in reversed(topo):  # 逆序处理到 node 时其所有后继已处理完毕
        for nxt in adj[node]:
            if lb[node] < lb[nxt] + 1:
                lb[node] = lb[nxt] + 1
    return lb, ub


def lexicographic_order(ids: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """按古老到年轻排列、编号字典序最小的合法（拓扑）顺序。

    Kahn 算法 + 最小堆：每步在入度为 0 的编号中取字典序最小者。
    """
    adj = _build_adj(ids, edges)
    indeg = {i: 0 for i in ids}
    for older, younger in edges:
        indeg[younger] += 1
    heap = [i for i in ids if indeg[i] == 0]
    heapq.heapify(heap)
    order: list[str] = []
    while heap:
        node = heapq.heappop(heap)
        order.append(node)
        for nxt in adj[node]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                heapq.heappush(heap, nxt)
    return order


def audit_strata(strata, relations):
    """主入口：依次执行 环检测 -> 区间传播 -> 合法性排序。"""
    ids = [s.id for s in strata]
    lower = {s.id: s.min_age for s in strata}
    upper = {s.id: s.max_age for s in strata}
    edges = [(r.older, r.younger) for r in relations]

    cycle = find_cycle_path(ids, edges)
    if cycle is not None:
        return CycleFound(cycle)

    lb, ub = tighten_intervals(ids, lower, upper, edges)
    emptied = [(i, lb[i], ub[i]) for i in ids if lb[i] > ub[i]]
    if emptied:
        return ConflictFound(emptied)

    return Solved(
        intervals={i: (lb[i], ub[i]) for i in ids},
        order=lexicographic_order(ids, edges),
    )
