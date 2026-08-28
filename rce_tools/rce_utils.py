def days_since_jan1_to_month_day(days_since_jan1, iyear, calendar="noleap"):
    """
    Returns the month and day (as integers) given the number of days since Jan 1st.
    For days_since_jan1=0, returns (1, 1) i.e., Jan 01.
    """
    import datetime
    if calendar == "noleap":
        days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        rem = int(days_since_jan1)
        m = 1
        for dim in days_in_month:
            if rem < dim:
                d = rem + 1
                return m, d
            rem -= dim
            m += 1
        raise ValueError("Days exceeded year length")
    elif calendar == "standard":
        dt = datetime.datetime(iyear, 1, 1) + datetime.timedelta(days=int(days_since_jan1))
        return dt.month, dt.day
    else:
        raise ValueError(f"Unknown calendar: {calendar}")

def month_day_to_days_since_jan1(month, day, iyear, calendar="noleap"):
    """
    Returns the number of days since Jan 1st given the month, day, and year.
    For Jan 01 (month=1, day=1), returns 0.
    """
    import datetime
    if calendar == "noleap":
        days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if month < 1 or month > 12:
            raise ValueError(f"Invalid month: {month}")
        if day < 1 or day > days_in_month[month - 1]:
            raise ValueError(f"Invalid day {day} for month {month}")
        days = sum(days_in_month[:month-1]) + (day - 1)
        return days
    elif calendar == "standard":
        dt = datetime.datetime(iyear, month, day)
        dt_start = datetime.datetime(iyear, 1, 1)
        return (dt - dt_start).days
    else:
        raise ValueError(f"Unknown calendar: {calendar}")
