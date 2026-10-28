import math
from typing import List, Dict, Optional, Tuple


def calculate_signed_error(forecast: float, actual: float) -> float:
    """
    Computes signed forecast error e_t = F_t - A_t.
    Positive value indicates over-forecasting (forecast > actual).
    Negative value indicates under-forecasting (actual > forecast).
    """
    return float(forecast - actual)


def calculate_mae(forecasts: List[float], actuals: List[float]) -> float:
    """
    Mean Absolute Error (MAE): mean(|F_t - A_t|)
    Raises ValueError on empty or mismatched lists.
    """
    if not forecasts or not actuals:
        raise ValueError("Cannot calculate MAE on empty lists.")
    if len(forecasts) != len(actuals):
        raise ValueError(f"Mismatched lengths: forecasts ({len(forecasts)}) != actuals ({len(actuals)}).")
    
    total_abs_err = sum(abs(f - a) for f, a in zip(forecasts, actuals))
    return float(total_abs_err / len(forecasts))


def calculate_rmse(forecasts: List[float], actuals: List[float]) -> float:
    """
    Root Mean Squared Error (RMSE): sqrt(mean((F_t - A_t)^2))
    Raises ValueError on empty or mismatched lists.
    """
    if not forecasts or not actuals:
        raise ValueError("Cannot calculate RMSE on empty lists.")
    if len(forecasts) != len(actuals):
        raise ValueError(f"Mismatched lengths: forecasts ({len(forecasts)}) != actuals ({len(actuals)}).")
    
    total_sq_err = sum((f - a) ** 2 for f, a in zip(forecasts, actuals))
    return float(math.sqrt(total_sq_err / len(forecasts)))


def calculate_mean_signed_error(forecasts: List[float], actuals: List[float]) -> float:
    """
    Mean Signed Error (Bias): mean(F_t - A_t)
    Positive indicates systematic over-forecasting.
    Negative indicates systematic under-forecasting.
    """
    if not forecasts or not actuals:
        raise ValueError("Cannot calculate Mean Signed Error on empty lists.")
    if len(forecasts) != len(actuals):
        raise ValueError(f"Mismatched lengths: forecasts ({len(forecasts)}) != actuals ({len(actuals)}).")
    
    total_signed_err = sum(f - a for f, a in zip(forecasts, actuals))
    return float(total_signed_err / len(forecasts))


def calculate_max_absolute_error(forecasts: List[float], actuals: List[float]) -> float:
    """
    Maximum Absolute Error: max(|F_t - A_t|)
    """
    if not forecasts or not actuals:
        raise ValueError("Cannot calculate Max Absolute Error on empty lists.")
    if len(forecasts) != len(actuals):
        raise ValueError(f"Mismatched lengths: forecasts ({len(forecasts)}) != actuals ({len(actuals)}).")
    
    return float(max(abs(f - a) for f, a in zip(forecasts, actuals)))


def calculate_wape(forecasts: List[float], actuals: List[float]) -> Optional[float]:
    """
    Weighted Absolute Percentage Error (WAPE):
    sum(|F_t - A_t|) / sum(A_t) * 100%
    Safe against individual zero-actual periods because sum(A_t) is aggregate.
    Returns None if sum(actuals) is zero.
    """
    if not forecasts or not actuals:
        return None
    sum_actual = sum(actuals)
    if sum_actual <= 0:
        return None
    sum_abs_err = sum(abs(f - a) for f, a in zip(forecasts, actuals))
    return float((sum_abs_err / sum_actual) * 100.0)


def calculate_conditional_mape(
    forecasts: List[float],
    actuals: List[float],
    min_actual_threshold: float = 100.0
) -> Tuple[Optional[float], int]:
    """
    Computes MAPE strictly for periods where actual generation >= threshold.
    Prevents infinite or severely distorted percentage errors when wind is near zero.
    Returns (mape_value, valid_period_count).
    """
    if not forecasts or not actuals:
        return None, 0
    
    valid_ratios = []
    for f, a in zip(forecasts, actuals):
        if a >= min_actual_threshold:
            valid_ratios.append(abs(f - a) / a)
            
    if not valid_ratios:
        return None, 0
    
    mape = (sum(valid_ratios) / len(valid_ratios)) * 100.0
    return float(mape), len(valid_ratios)


def compute_error_distribution(
    errors: List[float],
    bucket_count: int = 10
) -> List[Dict]:
    """
    Calculates histogram distribution buckets for signed forecast errors.
    """
    if not errors:
        return []
    
    min_e = min(errors)
    max_e = max(errors)
    
    if min_e == max_e:
        return [{
            "range_label": f"{round(min_e, 1)} MW",
            "min_val": round(min_e, 2),
            "max_val": round(max_e, 2),
            "count": len(errors),
            "percentage": 100.0
        }]
    
    step = (max_e - min_e) / bucket_count
    buckets = []
    
    for i in range(bucket_count):
        b_min = min_e + i * step
        b_max = min_e + (i + 1) * step if i < bucket_count - 1 else max_e
        
        if i == bucket_count - 1:
            count = sum(1 for e in errors if b_min <= e <= b_max)
        else:
            count = sum(1 for e in errors if b_min <= e < b_max)
            
        pct = (count / len(errors)) * 100.0
        buckets.append({
            "range_label": f"{int(b_min)} to {int(b_max)} MW",
            "min_val": round(b_min, 1),
            "max_val": round(b_max, 1),
            "count": count,
            "percentage": round(pct, 2)
        })
        
    return buckets
