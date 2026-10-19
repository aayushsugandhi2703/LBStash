from bt.contracts import MonthlySchedule, WeeklySchedule, YearlySchedule
from bt_recurring.schedule import first_occurrence, is_real_date, next_occurrence


def monthly(day: int) -> MonthlySchedule:
    return MonthlySchedule(kind='monthly', day=day)


class TestMonthlySchedules:
    def test_first_occurrence_is_on_or_after_the_start_day(self):
        assert first_occurrence(monthly(1), '2026-10-18') == '2026-11-01'
        assert first_occurrence(monthly(1), '2026-11-01') == '2026-11-01'
        assert first_occurrence(monthly(20), '2026-10-18') == '2026-10-20'
        assert first_occurrence(monthly(5), '2026-12-18') == '2027-01-05'

    def test_the_31st_clamps_in_short_months_but_comes_back_to_the_31st(self):
        seen: list[str] = []
        d = '2026-01-31'
        for _ in range(5):
            seen.append(d)
            d = next_occurrence(monthly(31), d)
        assert seen == ['2026-01-31', '2026-02-28', '2026-03-31', '2026-04-30', '2026-05-31']

    def test_february_in_leap_and_non_leap_years_incl_century_rules(self):
        assert next_occurrence(monthly(30), '2028-01-30') == '2028-02-29'
        assert next_occurrence(monthly(29), '2027-01-29') == '2027-02-28'
        assert next_occurrence(monthly(29), '2028-01-29') == '2028-02-29'
        assert next_occurrence(monthly(29), '2100-01-29') == '2100-02-28'  # 2100 is not a leap year
        assert next_occurrence(monthly(29), '2000-01-29') == '2000-02-29'  # 2000 is
        assert next_occurrence(monthly(31), '2028-02-29') == '2028-03-31'

    def test_a_start_in_a_short_month_on_the_31st_lands_on_its_last_day(self):
        assert first_occurrence(monthly(31), '2026-02-10') == '2026-02-28'
        assert first_occurrence(monthly(31), '2026-02-28') == '2026-02-28'
        assert first_occurrence(monthly(31), '2026-03-01') == '2026-03-31'

    def test_rolls_over_the_year(self):
        assert next_occurrence(monthly(15), '2026-12-15') == '2027-01-15'


class TestWeeklySchedules:
    monday = WeeklySchedule(kind='weekly', weekday=1)

    def test_finds_the_next_weekday_and_then_steps_7_days(self):
        assert first_occurrence(self.monday, '2026-10-18') == '2026-10-19'  # a Sunday
        assert first_occurrence(self.monday, '2026-10-19') == '2026-10-19'
        assert next_occurrence(self.monday, '2026-10-19') == '2026-10-26'
        assert next_occurrence(self.monday, '2026-12-28') == '2027-01-04'

    def test_sunday_is_0_and_saturday_is_6(self):
        assert first_occurrence(WeeklySchedule(kind='weekly', weekday=0), '2026-10-19') == '2026-10-25'
        assert first_occurrence(WeeklySchedule(kind='weekly', weekday=6), '2026-10-19') == '2026-10-24'


class TestYearlySchedules:
    def test_same_day_next_year_feb_29_clamps_to_the_28th_outside_leap_years(self):
        y = YearlySchedule(kind='yearly', month=2, day=29)
        assert first_occurrence(y, '2027-01-01') == '2027-02-28'
        assert next_occurrence(y, '2027-02-28') == '2028-02-29'
        assert next_occurrence(y, '2028-02-29') == '2029-02-28'
        d = YearlySchedule(kind='yearly', month=12, day=25)
        assert first_occurrence(d, '2026-12-26') == '2027-12-25'
        assert next_occurrence(d, '2026-12-25') == '2027-12-25'


class TestDates:
    def test_rejects_dates_that_do_not_exist(self):
        assert is_real_date('2026-02-31') is False
        assert is_real_date('2026-13-01') is False
        assert is_real_date('2028-02-29') is True
        assert is_real_date('2026-2-3') is False
