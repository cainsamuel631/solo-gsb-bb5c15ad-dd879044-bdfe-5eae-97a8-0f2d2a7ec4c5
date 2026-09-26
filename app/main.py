"""FastAPI 应用入口。"""
from __future__ import annotations

import os

from fastapi import FastAPI

from app.models import AuditRequest, AuditResponse, ConflictOut, IntervalOut
from app.solver import ConflictFound, CycleFound, Solved, audit_strata

app = FastAPI(
    title="年代约束审计 API",
    version="1.0.0",
    summary="审计地层年代区间与“甲比乙古老”观测关系的一致性",
    description=(
        "提交编号唯一的地层及其允许的整数年代区间（百万年，数值越大越古老），"
        "以及“甲比乙古老”的观测关系（转为 age(甲) >= age(乙) + 1）。"
        "服务检测关系环、沿关系图传播收紧各地层区间，"
        "可行时返回收紧后的区间与按古老到年轻、编号字典序最小的合法顺序。"
    ),
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/audit", response_model=AuditResponse, tags=["audit"])
def audit(request: AuditRequest) -> AuditResponse:
    result = audit_strata(request.strata, request.relations)

    if isinstance(result, CycleFound):
        return AuditResponse(status="cycle", cycle=result.path)

    if isinstance(result, ConflictFound):
        return AuditResponse(
            status="conflict",
            conflicts=[
                ConflictOut(id=sid, min_age=lb, max_age=ub)
                for sid, lb, ub in result.emptied
            ],
        )

    assert isinstance(result, Solved)
    return AuditResponse(
        status="ok",
        intervals={
            sid: IntervalOut(min_age=lo, max_age=hi)
            for sid, (lo, hi) in result.intervals.items()
        },
        order=result.order,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
