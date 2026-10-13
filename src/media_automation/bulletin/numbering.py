"""Date-based weekly issue number, anchored to the confirmed 2026-10-11 13-41."""
from datetime import date, timedelta

def number_for_date(value):
    day=date.fromisoformat(value) if isinstance(value,str) else value
    if day.weekday()!=6:raise ValueError('주보 날짜는 주일이어야 합니다.')
    first=date(day.year,1,1)
    first+=timedelta(days=(6-first.weekday())%7)
    return f'{13+day.year-2026}-{1+(day-first).days//7}'
