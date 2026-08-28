# Inputs: Date of Event, Start Time, End Time
from mce_baseline_functions import *


raw_data = (pl.read_parquet('demo_data.parquet')
              .with_columns(pl.lit(0).alias('outage_flag')))


with pl.Config(tbl_rows=48):
        print(raw_data.sort(['site_id', 'datetime']).head(48))

# sys.exit(0)
# Optional overrides to defaults for fake data:
# Parameters that can change:
# - 'temp_col' can be 'mean_temp', 'max_temp', or 'min_temp'
# - 'top_n' is the number of days in each month that are flagged.
# - 'flag_pct' is the percent of days be flagged as events.

# For example, the following would create a very high event frequency,
# with the 80% of top 20 days in each month being flagged as an "event."
# While not realistic or rare, this is good to test the more nuanced
# rules of the baseline, such as using "reserve" days.

test_proxy_day_parms = {'top_n': 20,
                        'flag_pct': .8}

# test_proxy_day_parms = {} # Uncomment this to use defaults. Alternately, remove the kwars from function invocation.

baseline_test_data = create_fake_baseline_inputs(df=raw_data,
                                                 random_seed=50,
                                                 **test_proxy_day_parms)


print(f'There are {baseline_test_data.select(pl.n_unique('site_id'))} unique IDs available.')
# Select an ID number to run (this is an index value, 
# not the actual ID number, which are not consecutive).
id_number = 5 

single_id_data = single_site_subset(baseline_test_data, id_number)


with pl.Config(tbl_rows=48):
        print(single_id_data.sort(['site_id', 'datetime']).head(48))


# sys.exit(0)
with pl.Config(tbl_rows=1):
    # print(f'Single ID Data Head: {single_id_data.sort('datetime').head(5)}')
    print(baseline_test_data
          .with_columns(pl.col('datetime').cast(pl.Date).alias('date'))
          .with_columns((pl.col('datetime').dt.weekday().is_in([6, 7])).alias('weekend'))
          .group_by(['date', 'weekend', 'event_day_flag'])
          .agg(pl.count('site_id'))
          .sort(['date', 'event_day_flag']))
    

proxy_dates = sorted(single_id_data
                     .filter(pl.col('event_day_flag')==pl.lit(1))
                     .select(pl.col('datetime').cast(pl.Date).alias('date'))
                     .unique()
                     .to_series()
                     .to_list())

# To identify which of the proxy days are on weekends, for testing selection, you can uncomment and run this:
# for i, d in enumerate(proxy_dates):
#         print(f'Set proxy_n to {i}, for {d}, with is weekday {d.weekday()}, weekend={d.weekday() in [5, 6]}')

# Here you can set the proxy day used and the event hours.
# This number will align with different days if the data creation parameters are changed.
# It is only for demonstration purposes.

proxy_n = 79 

proxy_date = proxy_dates[min(proxy_n, len(proxy_dates)-1)]

event_hours_ending = [17, 18]



# Execution of the function for a single site:
(input_data, input_subset, selected_days, event_and_baseline) = bsln_10_in_10(indf=single_id_data,
                                                                              event_date=proxy_date,
                                                                              event_hours=event_hours_ending,
                                                                              holiday_list=nerc_holidays,
                                                                              full_verbosity=True)



with pl.Config(tbl_rows=48, tbl_cols=20):
        print(event_and_baseline.sort(['site_id', 'hour_ending']).head(48))


# Graph of the baseline. If in interactive mode, the plot should appear in the IDE. 
# If run in terminal, the plot should be surfaced in a browser.
single_baseline_plot(event_and_baseline)

# If you want to copy the various output to Excel, these will copy to the clipboard and you can just paste into Excel.
# (input_data.sort(['site_id', 'date']).to_pandas().to_clipboard())
# (selected_days.sort(['site_id', 'day_group', 'selection_order']).to_pandas().to_clipboard())
# (input_subset.sort(['site_id', 'day_group', 'selection_order']).to_pandas().to_clipboard())
# (event_and_baseline.sort(['site_id', 'hour_ending']).to_pandas().to_clipboard())

