"""Optional scikit-learn adapter, imported only when training is requested."""

def model_types():
    try:
        from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
        from sklearn.linear_model import LinearRegression
    except ImportError as exc:
        raise RuntimeError(
            "Forecasting dependencies are missing. Install with: "
            "python -m pip install -e '.[forecast]'"
        ) from exc

    return LinearRegression, RandomForestRegressor, GradientBoostingRegressor
