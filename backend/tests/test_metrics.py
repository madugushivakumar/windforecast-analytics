import math
import pytest
from app.analytics.metrics import (
    calculate_signed_error,
    calculate_mae,
    calculate_rmse,
    calculate_mean_signed_error,
    calculate_max_absolute_error,
    calculate_wape,
    calculate_conditional_mape,
    compute_error_distribution,
)


def test_calculate_signed_error():
    assert calculate_signed_error(120.0, 100.0) == 20.0  # Over-forecast
    assert calculate_signed_error(80.0, 100.0) == -20.0  # Under-forecast
    assert calculate_signed_error(100.0, 100.0) == 0.0   # Perfect


def test_perfect_forecasts():
    forecasts = [100.0, 250.0, 500.0, 1000.0]
    actuals = [100.0, 250.0, 500.0, 1000.0]

    assert calculate_mae(forecasts, actuals) == 0.0
    assert calculate_rmse(forecasts, actuals) == 0.0
    assert calculate_mean_signed_error(forecasts, actuals) == 0.0
    assert calculate_max_absolute_error(forecasts, actuals) == 0.0
    assert calculate_wape(forecasts, actuals) == 0.0


def test_hand_calculated_metrics():
    # Hand-calculated case:
    # F = [100.0, 150.0, 200.0]
    # A = [80.0, 150.0, 250.0]
    # e = [+20.0, 0.0, -50.0]
    # |e| = [20.0, 0.0, 50.0] -> sum = 70.0 -> MAE = 70/3 = 23.333333...
    # e^2 = [400.0, 0.0, 2500.0] -> sum = 2900.0 -> mean = 966.666667 -> RMSE = 31.09126...
    # sum e = -30.0 -> Bias = -10.0
    # max |e| = 50.0
    # WAPE = sum(|e|) / sum(A) = 70.0 / 480.0 * 100 = 14.58333...%
    forecasts = [100.0, 150.0, 200.0]
    actuals = [80.0, 150.0, 250.0]

    mae = calculate_mae(forecasts, actuals)
    assert pytest.approx(mae, 0.0001) == 70.0 / 3.0

    rmse = calculate_rmse(forecasts, actuals)
    assert pytest.approx(rmse, 0.0001) == math.sqrt(2900.0 / 3.0)

    bias = calculate_mean_signed_error(forecasts, actuals)
    assert pytest.approx(bias, 0.0001) == -10.0

    max_abs = calculate_max_absolute_error(forecasts, actuals)
    assert max_abs == 50.0

    wape = calculate_wape(forecasts, actuals)
    assert pytest.approx(wape, 0.0001) == (70.0 / 480.0) * 100.0


def test_empty_lists_raise_value_error():
    with pytest.raises(ValueError, match="empty"):
        calculate_mae([], [])

    with pytest.raises(ValueError, match="empty"):
        calculate_rmse([], [])

    with pytest.raises(ValueError, match="empty"):
        calculate_mean_signed_error([], [])

    with pytest.raises(ValueError, match="empty"):
        calculate_max_absolute_error([], [])


def test_mismatched_lengths_raise_value_error():
    with pytest.raises(ValueError, match="Mismatched lengths"):
        calculate_mae([100.0], [100.0, 200.0])

    with pytest.raises(ValueError, match="Mismatched lengths"):
        calculate_rmse([100.0, 200.0], [100.0])


def test_zero_actuals_mape_handling():
    # Actual has 0.0 MW
    forecasts = [50.0, 200.0]
    actuals = [0.0, 200.0]

    # Standard MAPE with threshold 100.0 ignores the 0.0 MW period safely
    mape, count = calculate_conditional_mape(forecasts, actuals, min_actual_threshold=100.0)
    assert count == 1
    assert mape == 0.0  # period 2 has F=200, A=200 -> 0% error

    # WAPE safely handles sum of actuals
    wape = calculate_wape(forecasts, actuals)
    # sum |e| = 50 + 0 = 50; sum A = 0 + 200 = 200 -> 25%
    assert wape == 25.0


def test_error_distribution_buckets():
    errors = [-100.0, -50.0, 0.0, 50.0, 100.0]
    buckets = compute_error_distribution(errors, bucket_count=5)
    assert len(buckets) == 5
    total_count = sum(b["count"] for b in buckets)
    assert total_count == 5
