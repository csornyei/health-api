from typing import Literal

from pydantic import BaseModel


class DailyMetric(BaseModel):
    daily: list[float | None]
    avg: float | None


class TrendMetric(DailyMetric):
    trend: Literal["improving", "stable", "worsening"]


class WristTemp(BaseModel):
    daily: list[float | None]
    baseline: float | None
    deviations: list[float | None]


class Recovery(BaseModel):
    hrv: TrendMetric
    resting_hr: TrendMetric
    respiratory_rate: DailyMetric
    spo2: DailyMetric
    breathing_disturbances: DailyMetric
    wrist_temp: WristTemp


class SleepNight(BaseModel):
    date: str
    total_h: float
    deep_h: float
    rem_h: float
    core_h: float
    awake_h: float
    efficiency_pct: float | None
    sleep_start: str
    sleep_end: str


class SleepSummary(BaseModel):
    avg_total_h: float | None
    avg_deep_h: float | None
    avg_rem_h: float | None
    avg_efficiency_pct: float | None


class HrRecoveryPoint(BaseModel):
    time: str
    min_bpm: int
    avg_bpm: int
    max_bpm: int


class WorkoutOut(BaseModel):
    type: str
    date: str
    start_time: str
    duration_min: int
    distance_km: float | None
    avg_hr_bpm: int | None
    max_hr_bpm: int | None
    active_kcal: int
    hr_recovery: list[HrRecoveryPoint]


class ActivityMetric(BaseModel):
    daily: list[float | None]
    total: int
    avg: int


class Training(BaseModel):
    workouts: list[WorkoutOut]
    active_kcal: ActivityMetric
    exercise_min: ActivityMetric
    steps: ActivityMetric
    total_distance_km: float


class Energy(BaseModel):
    active_kcal_daily: list[float | None]
    basal_kcal_daily: list[float | None]
    tdee_daily: list[float | None]
    avg_tdee: int | None


class Fitness(BaseModel):
    vo2_max_current: float | None
    vo2_max_prior: float | None
    vo2_max_delta: float | None


class Body(BaseModel):
    weight_kg: DailyMetric | None
    body_fat_pct: DailyMetric | None


class SummaryMeta(BaseModel):
    period_start: str
    period_end: str
    summary_type: str
    days: int


class NutritionStat(BaseModel):
    daily: list[float | None]
    total: float | None


class Nutrition(BaseModel):
    vitamin_b12: NutritionStat
    saturated_fat: NutritionStat
    total_fat: NutritionStat
    fiber: NutritionStat
    protein: NutritionStat
    dietary_energy: NutritionStat
    carbohydrates: NutritionStat


class SummaryResponse(BaseModel):
    meta: SummaryMeta
    recovery: Recovery
    sleep: list[SleepNight]
    sleep_summary: SleepSummary
    training: Training
    energy: Energy
    fitness: Fitness
    body: Body
    nutrition: Nutrition
