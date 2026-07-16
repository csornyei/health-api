from typing import Optional, Union

from pydantic import BaseModel, Field

# ── Shared ─────────────────────────────────────────────────────────────────


class ValueWithUnits(BaseModel):
    qty: float
    units: str


# ── Metric data points ─────────────────────────────────────────────────────


class QuantityDataPoint(BaseModel):
    source: str
    date: str
    qty: float


class HeartRateMetricPoint(BaseModel):
    """Daily heart rate summary (min/avg/max) from the metrics array."""

    source: str
    date: str
    Min: float
    Avg: float
    Max: float


class SleepDataPoint(BaseModel):
    source: str
    date: str
    sleepStart: str
    sleepEnd: str
    inBedStart: str
    inBedEnd: str
    totalSleep: float
    core: float
    deep: float
    rem: float
    awake: float
    inBed: float
    asleep: float


# Union tries left-to-right; most-specific first so Pydantic picks the right model.
MetricDataPoint = Union[SleepDataPoint, HeartRateMetricPoint, QuantityDataPoint]


class Metric(BaseModel):
    name: str
    units: Optional[str] = None
    data: list[MetricDataPoint]


class NutritionMetric(BaseModel):
    name: str
    units: Optional[str] = None
    data: list[QuantityDataPoint]


# ── Workout structures ─────────────────────────────────────────────────────


class WorkoutHeartRatePoint(BaseModel):
    """Per-interval heart rate sample inside a workout."""

    source: str
    date: str
    Min: float
    Avg: float
    Max: float
    units: str


class WorkoutTimeSeriesPoint(BaseModel):
    """Generic per-interval sample with a quantity and units (energy, distance, steps)."""

    source: str
    date: str
    qty: float
    units: str


class HeartRateSummary(BaseModel):
    avg: ValueWithUnits
    min: ValueWithUnits
    max: ValueWithUnits


class Workout(BaseModel):
    id: str
    name: str
    start: str
    end: str
    duration: float
    distance: ValueWithUnits
    speed: ValueWithUnits
    stepCadence: ValueWithUnits
    activeEnergyBurned: ValueWithUnits
    avgHeartRate: Optional[ValueWithUnits] = None
    maxHeartRate: Optional[ValueWithUnits] = None
    heartRate: Optional[HeartRateSummary] = None
    heartRateData: list[WorkoutHeartRatePoint] = Field(default_factory=list)
    heartRateRecovery: list[WorkoutHeartRatePoint] = Field(default_factory=list)
    activeEnergy: list[WorkoutTimeSeriesPoint]
    walkingAndRunningDistance: list[WorkoutTimeSeriesPoint]
    stepCount: list[WorkoutTimeSeriesPoint]


# ── Root ───────────────────────────────────────────────────────────────────


class MetricsData(BaseModel):
    metrics: list[Metric]


class MetricsExport(BaseModel):
    data: MetricsData


class WorkoutsData(BaseModel):
    workouts: list[Workout]


class NutritionData(BaseModel):
    metrics: list[NutritionMetric]


class NutritionExport(BaseModel):
    data: NutritionData


class WorkoutsExport(BaseModel):
    data: WorkoutsData
