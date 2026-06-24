import pandas as pd

DOMESTIC_MERCHANTS = ['swiggy', 'ola', 'irctc', 'zomato', 'flipkart', 'myntra']


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    df['is_anomaly'] = False
    df['anomaly_reason'] = None

    # 1. Flag amount > 3x account median
    medians = df.groupby('account_id')['amount'].median()

    def check_amount_anomaly(row):
        try:
            median = medians.get(row['account_id'], None)
            amount = row['amount']
            if pd.notna(median) and median > 0 and pd.notna(amount) and amount > 3 * median:
                return True, f"Amount {row['amount']} exceeds 3x account median {median}"
        except:
            pass
        return False, None

    for idx, row in df.iterrows():
        is_anom, reason = check_amount_anomaly(row)
        if is_anom:
            df.at[idx, 'is_anomaly'] = True
            df.at[idx, 'anomaly_reason'] = reason

    # 2. Flag USD transactions with domestic merchants
    for idx, row in df.iterrows():
        try:
            merchant = str(row['merchant']).lower().strip()
            currency = str(row['currency']).upper().strip()
            if currency == 'USD' and any(m in merchant for m in DOMESTIC_MERCHANTS):
                df.at[idx, 'is_anomaly'] = True
                existing = df.at[idx, 'anomaly_reason'] or ''
                df.at[idx, 'anomaly_reason'] = (
                        existing + f" | USD currency used with domestic merchant '{row['merchant']}'"
                ).strip(' |')
        except:
            pass

    return df
