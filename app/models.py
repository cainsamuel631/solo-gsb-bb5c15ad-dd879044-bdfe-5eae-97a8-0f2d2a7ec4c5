"""请求 / 响应的数据模型（Pydantic v2）。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Stratum(BaseModel):
    """一个地层及其允许的整数年代区间（单位：百万年，数值越大越古老）。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64, description="地层编号，全局唯一")
    min_age: int = Field(ge=0, description="区间下界：允许的最小年代（最年轻）")
    max_age: int = Field(ge=0, description="区间上界：允许的最大年代（最古老）")

    @model_validator(mode="after")
    def _check_interval(self) -> "Stratum":
        if self.min_age > self.max_age:
            raise ValueError("min_age 不能大于 max_age（区间为空）")
        return self


class Relation(BaseModel):
    """一条“甲比乙古老”的观测关系，语义为 age(older) >= age(younger) + 1。"""

    model_config = ConfigDict(extra="forbid")

    older: str = Field(min_length=1, description="较古老的一方（甲）")
    younger: str = Field(min_length=1, description="较年轻的一方（乙）")

    @model_validator(mode="after")
    def _check_not_self(self) -> "Relation":
        if self.older == self.younger:
            raise ValueError("同一地层不得比自身古老（older 与 younger 相同）")
        return self


class AuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strata: list[Stratum] = Field(min_length=1, description="地层及其允许年代区间")
    relations: list[Relation] = Field(default_factory=list, description="观测到的古老关系")

    @model_validator(mode="after")
    def _check_ids(self) -> "AuditRequest":
        ids = [s.id for s in self.strata]
        if len(ids) != len(set(ids)):
            raise ValueError("地层编号必须唯一，存在重复编号")
        known = set(ids)
        referenced = {r.older for r in self.relations} | {r.younger for r in self.relations}
        unknown = sorted(referenced - known)
        if unknown:
            raise ValueError(f"关系引用了未登记的地层编号: {', '.join(unknown)}")
        return self


class IntervalOut(BaseModel):
    min_age: int = Field(description="收紧后的区间下界（最年轻）")
    max_age: int = Field(description="收紧后的区间上界（最古老）")


class ConflictOut(BaseModel):
    id: str = Field(description="区间被压空的地层编号")
    min_age: int = Field(description="传播后的下界（已大于 max_age）")
    max_age: int = Field(description="传播后的上界")


class AuditResponse(BaseModel):
    status: Literal["ok", "cycle", "conflict"] = Field(
        description="ok=可行；cycle=关系成环；conflict=区间被压空"
    )
    cycle: list[str] | None = Field(
        default=None, description="成环时的地层编号路径，首尾相同"
    )
    conflicts: list[ConflictOut] | None = Field(
        default=None, description="区间被压空的冲突地层列表"
    )
    intervals: dict[str, IntervalOut] | None = Field(
        default=None, description="可行时各地层收紧后的区间"
    )
    order: list[str] | None = Field(
        default=None, description="可行时按古老到年轻排列、编号字典序最小的合法顺序"
    )
