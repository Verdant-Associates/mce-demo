
import numpy as np
import polars as pl
import holidays 
import datetime
import holidays
import plotly.graph_objects as go

import sys
# import re 


'''
These functions have been made temporarily available on GitHub, accompanied by:
- A PowerShell script that will create a virtual environment with the necessary packages.
- A parquet file of demo data. 
- A Python script that allows one to test the scripts, changing IDs, proxy dates, etc.

https://github.com/Verdant-Associates/mce-demo

See the README for details, but for those interested in executing the code, we 
have provided this capabilty.

The core function for the baseline is bsln_10_in_10, but there are several utility functions
that are used in all of the baseline types as well as functions to create fake data
for testing.

Note that these functions have been extracted from a broader pipeline runs all baseline types.
Withing that framework we have built try and except functionality to handle errors.

'''
def pivot_tall_to_wide(tall_df: pl.DataFrame, 
                       pivot_cols: list,
                       index_cols: list=['site_id', 'event_date', 'date', 'event_day_flag', 'outage_flag']) -> pl.DataFrame:
    ''' Utility function to transform the input data from the tall version to wide.
    '''
    return (tall_df
            .with_columns((pl.col('datetime').dt.hour() + 1).alias('he'))
            # .with_columns(pl.format('obs_{}00', pl.col('he').cast(pl.Utf8).str.zfill(2)).alias('col_name'))
            .with_columns(('obs_' + pl.col('he').cast(pl.Utf8).str.zfill(2) + '00').alias('col_name'))
            .sort(index_cols + ['he'])
            .pivot(index=index_cols,
                    on='col_name',
                    values='observed')
            .select(index_cols + pivot_cols))

def pivot_wide_to_tall(tall_df: pl.DataFrame, 
                       pivot_cols: list,
                       first_index_cols:list=['site_id', 'event_date', 'adj_numer', 'adj_denom', 'series_type'],
                       second_index_cols:list=['site_id', 'event_date', 'adj_numer', 'adj_denom', '_name_']) -> pl.DataFrame:
    ''' Utility function to transform the wide version to tall.
    '''
    # wide (kwh_HHMM columns) -> long, then long -> wide split into event_day / baseline columns
    unpivot = tall_df.unpivot(
        index=first_index_cols,
        on=pivot_cols,
        variable_name='_name_',
        value_name='series')

    return(unpivot.pivot(
        index=second_index_cols,
        on='series_type',
        values='series'))
    

def bsln_10_in_10(indf: pl.DataFrame=None, 
                  event_date: datetime.date=None, 
                  event_hours: list[str]=None,
                  holiday_list: list=None,
                  full_verbosity: bool=False,
                  **kwargs) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    ''' Calculates the 
        Required columns in indf:
        {'site_id': Int64, 
         'datetime': Datetime(time_unit='ns', time_zone=None), 
         'observed': Float64, 
         'event_day_flag': Int8}

         Use to kwargs argument to override CAISO defaults.
         Valild keys to override:
         - days_prior
         - weekday_target_days
         - weekend_target_days
         - weekday_minimum_days
         - weekend_minimum_days

    '''
    observed_load_cols = [f'obs_{h:02d}00' for h in range(1, 25)]

    input_tall = (indf.clone()
                      .with_columns(pl.col('datetime').cast(pl.Date).alias('date'))
                      .with_columns((pl.col('datetime').dt.hour()+1).alias('hour_ending'))
                      .with_columns(pl.lit(event_date).alias('event_date')))
    
    input_data = pivot_tall_to_wide(input_tall, observed_load_cols)

    input_data = (input_data
                  .with_columns((pl.col('date') == event_date).cast(pl.Int64).alias('curr_event_flag')))

    # hour-ending columns are obs_0100 ... obs_2400; timestamps are hour-beginning
    event_hours_he = [int(h) for h in event_hours]
    event_hours_hb = [h - 1 for h in event_hours_he]
    event_hour_cols = [f'obs_{h:0>2d}00' for h in event_hours_he]

    # the second, third, and fourth hours preceding the event hour
    adjust_hours_hb = [min(event_hours_hb) + h for h in range(-4, -1)]
    adjust_hours_he = [h + 1 for h in adjust_hours_hb]
    adjust_hour_cols = [f'obs_{h:0>2d}00' for h in adjust_hours_he]

    if full_verbosity:

        print(f'Event Date {event_date=}')
        print(f'Event Hours {event_hours=}')        
        print('Event Hours (HB):', event_hours_hb)
        print('Event Hours (HE):', event_hours_he)
        print('Event Hour Cols:', event_hour_cols)
        print('Adjust Hours (HB):', adjust_hours_hb)
        print('Adjust Hours (HE):', adjust_hours_he)
        print('Adjust Hour Cols:', adjust_hour_cols)

    
    # CAISO rules being addressed:
    # "The calendar days for which the Meter Data will be collected will be determined by working 
    #  sequentially backwards from the Trading Day under examination up to a maximum of forty-five (45) calendar 
    #  days prior to the Trading Day"
    
    days_prior = kwargs.get('days_prior', 45) # 45 is CAISO default, so kwargs could be used to override.

    input_data = input_data.filter(pl.col('date').is_between(pl.lit(event_date).dt.offset_by(f'-{days_prior}d'), 
                                                             pl.lit(event_date)))

    event_day_tall = input_tall.filter(pl.col('date')==pl.lit(event_date))

    year_list = sorted(set(input_data.select(pl.col('date').dt.year()).to_series().unique().to_list()))
    holiday_df = create_holiday_df(year_list, holiday_list)

    day_type_subset = (input_data
                  .join(holiday_df, 
                        on='date', 
                        how='left')
                  .with_columns(pl.col('holiday').fill_null('NA'))
                  .with_columns([(pl.col('holiday') != 'NA').cast(pl.Int64).alias('holiday_flag'),
                                  pl.col('date').dt.weekday().alias('day_of_week')])
                  .with_columns(pl.col('day_of_week').is_in([6, 7]).cast(pl.Int64).alias('weekend_flag'))
                  .with_columns([(pl.max_horizontal(['weekend_flag', 'holiday_flag'])).alias('weekend_holiday_flag'),
                                 (pl.col('event_day_flag') == 1).cast(pl.Int64).alias('any_event_flag')])
                  .with_columns(pl.when(pl.col('curr_event_flag')==pl.lit(1))
                                  .then(pl.col('weekend_holiday_flag'))
                                  .alias('event_weekend_holiday_flag'))
                  .with_columns(pl.max('event_weekend_holiday_flag')
                                  .over(pl.col('site_id'))
                                  .alias('event_weekend_holiday_flag'))
                  # "including only business days if the Trading Day is a business day, including 
                  # only non-business days if the Trading Day is a non-business day...
                  .filter(pl.col('weekend_holiday_flag')==pl.col('event_weekend_holiday_flag')))

    # CAISO rules being adddressed:
    # The collection of Meter Data for this purpose stops upon reaching the target number of calendar days, which is 
    # ten (10) calendar days if the Trading Day is a 
    # business day or four (4) calendar days if the Trading Day is a non-business day.  If these targets cannot be met, 
    # a minimum of five (5) calendar days if the Trading Day is a business day or a minimum of four (4) calendar days 
    # if the Trading Day is a non-business day must be collected.  
    weekend_holiday_event = (day_type_subset.select(pl.max('event_weekend_holiday_flag')).item()==1)


    weekday_target_days = kwargs.get('weekday_target_days', 45) # 10 is CAISO default, so kwargs could be used to override.
    weekend_target_days = kwargs.get('weekend_target_days', 45) # 4 is CAISO default, so kwargs could be used to override.
    weekday_minimum_days = kwargs.get('weekday_minimum_days', 5) # 5 is CAISO default, so kwargs could be used to override.
    weekend_minimum_days = kwargs.get('weekend_minimum_days', 4) # 4 is CAISO default, so kwargs could be used to override.


    target_days = weekday_target_days if not weekend_holiday_event else weekend_target_days
    minimum_days = weekday_minimum_days if not weekend_holiday_event else weekend_minimum_days
     
    # CAISO rules being adddressed:
    # "Excluding calendar days on which the Proxy Demand Resource was subject to an Outage or 
    # previously provided Demand Response Services (other than 
    # capacity awarded for AS or RUC) or the Reliability Demand Response Resource was subject to an Outage as 
    # described in the Business Practice Manual"

    # If these targets cannot be met, Meter Data will be collected 
    # for the calendar days on which the Proxy Demand Resource was subject to an Outage or previously provided Demand 
    # Response Services (other than capacity awarded for AS or RUC) or the Reliability Demand Response Resource was subject 
    # to an Outage as described in the Business Practice Manual or previously provided Demand Response Services, and for 
    # which the amount of totalized load was highest during the hours when the Demand Response Services were provided in
    #  the forty-five (45) calendar days prior to the Trading Day.(b)   
    day_type_subset = (day_type_subset
                    .with_columns(pl.sum_horizontal(event_hour_cols).alias('event_hours_sum'))
                    .with_columns(pl.when(pl.col('curr_event_flag')==pl.lit(1)).then(pl.lit('01. Event Day'))
                                    .when(~((pl.col('any_event_flag')==pl.lit(1)) |
                                            (pl.col('outage_flag')==pl.lit(1))))
                                    .then(pl.lit('02. Elegible Days'))
                                    .otherwise(pl.lit('03. Reserve Days'))
                                    .alias('day_group'))
                    # Count of eligible (non-reserve, non-event) days available per id by the day group:
                    .with_columns([(pl.col('day_group')==pl.lit('02. Elegible Days')).cast(pl.Int32).alias('eligible_flag'),
                                   (pl.col('day_group')==pl.lit('03. Reserve Days')).cast(pl.Int32).alias('reserve_flag')])
                    .with_columns(pl.sum('eligible_flag').over('site_id').alias('total_eligible_days'))
                    .with_columns((pl.col('total_eligible_days')<pl.lit(target_days)).cast(pl.Int32).alias('need_reserve_flag')))

    # Establish sorting order for day selection based on day group:
    day_type_subset = (day_type_subset
                    .with_columns(pl.when(pl.col('curr_event_flag')==pl.lit(1))
                                    .then(pl.lit(0))
                                    .when(pl.col('eligible_flag')==pl.lit(1))
                                    .then(pl.col('date').rank(method='ordinal', descending=True).over(['site_id', 'day_group']))
                                    .when(pl.col('reserve_flag')==pl.lit(1))
                                    .then(pl.col('event_hours_sum').rank(method='ordinal', descending=True).over(['site_id', 'day_group']))
                                    .alias('selection_order'))
                    .sort(['site_id', 'day_group', 'selection_order'])
                    .with_columns(pl.when(pl.col('need_reserve_flag')==pl.lit(1))
                                    .then(pl.lit(minimum_days))
                                    .otherwise(pl.lit(target_days))
                                    .alias('selection_target'))
                    .with_columns(pl.cum_count('date').over('site_id').alias('selection_count')))


    selected_days = day_type_subset.filter(pl.col('selection_count')<=pl.col('selection_target'))

    event_and_baseline = (selected_days
                           .group_by(['site_id', 'event_date', 'curr_event_flag'])
                           .agg([pl.col(c).mean() for c in observed_load_cols] + [pl.count('date').alias('date_count')])
                           .with_columns((pl.col('curr_event_flag')==pl.lit(0)).cast(pl.Int32).alias('baseline_flag'))
                           .with_columns(pl.mean_horizontal(adjust_hour_cols).alias('adjust_hour_mean_use'))
                           .with_columns((pl.col('curr_event_flag') * pl.col('adjust_hour_mean_use')).max().over('site_id').alias('adj_numer'))
                           .with_columns((pl.col('baseline_flag') * pl.col('adjust_hour_mean_use')).max().over('site_id').alias('adj_denom'))
                           .with_columns(pl.when(pl.col('curr_event_flag')==pl.lit(1))
                                           .then(pl.lit('event_observed'))
                                           .otherwise(pl.lit('unadjusted_baseline'))
                                           .alias('series_type')))

    event_and_baseline = pivot_wide_to_tall(event_and_baseline, observed_load_cols)

    lower_adjust_cap = kwargs.get('lower_adjust_cap', .8)
    upper_adjust_cap = kwargs.get('upper_adjust_cap', 1.2)

    event_and_baseline = (event_and_baseline
                           .with_columns((pl.col('adj_numer') / pl.col('adj_denom'))
                                            .alias('raw_adjustment'))
                           .with_columns((pl.col('adj_numer') / pl.col('adj_denom'))
                                            .clip(lower_adjust_cap, upper_adjust_cap)
                                            .alias('capped_adjustment'))
                           .with_columns((pl.col('unadjusted_baseline') * pl.col('capped_adjustment')).alias('adjusted_baseline'))
                           .with_columns(pl.col('_name_').str.extract(r'(\d+)').cast(pl.Int32).floordiv(100).alias('hour_ending'))
                           .with_columns((pl.col('hour_ending').is_in([int(h) for h in event_hours])).cast(pl.Int32).alias('event_hour_flag'))
                           .with_columns((pl.col('hour_ending').is_in([int(h) for h in adjust_hours_he])).cast(pl.Int32).alias('adjust_hour_flag'))
                           .join(event_day_tall.select('site_id', 'hour_ending', 'temperature', 'ghi'),
                                 on=['site_id', 'hour_ending'],
                                 how='left'))
    
    print(event_and_baseline.select(pl.n_unique('site_id')).item())

    return input_data, day_type_subset, selected_days, event_and_baseline


# Holidays based on NERC, but can be customized as needed. 
# Use "Observed" versions when regular falls on a weekend:
nerc_holidays = ["New Year's Day", 
                 "New Year's Day (Observed)", 
                 # "Washington's Birthday", "Washington's Birthday (Observed)",
                 "Memorial Day",
                 "Independence Day", "Independence Day (Observed)",
                 "Labor Day",
                 "Veterans Day", "Veterans Day (Observed)",
                 "Thanksgiving",
                 #  "Day After Thanksgiving",
                 "Christmas Day", 
                 "Christmas Day (Observed)"]

def create_holiday_df(year_list:list, 
                      holiday_list:list, 
                      state:str='CA') -> pl.DataFrame:
    ''' For a list of year and holiday, returns a polars dataframe with
        date and holiday name. holiday_list should have the names associated
        with the holidays package. 
    '''
    holiday_items = [(d, name) for d, name in holidays.US(state=state, years=year_list).items()
                      if name in holiday_list]
    
    holiday_df = pl.DataFrame({
        'date': [d for d, _ in holiday_items],
        'holiday': [name for _, name in holiday_items]})
    return holiday_df


def single_site_subset(df: pl.DataFrame=None,
                       n: int=None) -> pl.DataFrame:
    ''' Subset the data to a single side.
        Since site_id is not consecutive, rather than guess at valid values, 
        just use the nth unique id, in order of first appearance.
    '''
    id = df.select(pl.col('site_id').unique(maintain_order=True))[n, 0]

    return df.filter(pl.col('site_id') == id)


def create_fake_baseline_inputs(df: pl.DataFrame=None,
                                random_seed:int=40,
                                **kwargs) -> pl.DataFrame:
    ''' Parquet file for demonstration is publicly available from the OpenDSM repository.
        It needs to be modified to represent DR events (proxy events in this case), 
        which is done in this function.  
    '''
    def flag_extreme_days_pl(daily_temps, temp_col, top_n, flag_pct, seed=random_seed):
        ''' For testing/demo, create proxy days using the top_n extreme days in each month,
            and flag a percentage of them. 
            Assumes for testing that all sites are dispatched on the same day.
            Actual execution could vary.
            To make the baseline calculation deal with high event frequency, 
            increase the top_n and flag_pct, which will lead to far more of the 
            days having event flags.
        '''
        winter_months = [11, 12, 1, 2]
        rng = np.random.default_rng(seed)

        extremes = (daily_temps
                   .with_columns(
                       pl.when(pl.col('month').is_in(winter_months))
                         .then(pl.col(temp_col))
                         .otherwise(-pl.col(temp_col))
                         .rank('ordinal')
                         .over(['month'])
                         .alias('rank_in_month'))
                   .filter(pl.col('rank_in_month') <= top_n)
                   .drop('rank_in_month'))

        return (extremes
                .with_columns(pl.Series('rand', rng.random(extremes.height)))
                .with_columns(
                    (pl.col('rand').rank('ordinal').over('month') <=
                     (pl.len().over('month') * flag_pct).round())
                    .cast(pl.Int8)
                    .alias('event_day_flag'))
                .drop('rand'))

    test_inputs = (df
              .with_columns(pl.col('datetime').cast(pl.Date).alias('date'))
              .unique(subset=['site_id', 'datetime'])
              .with_columns([pl.col('datetime').dt.month().alias('month')]))


    daily_temps = (test_inputs
                   .group_by(['month', 'date'])
                   .agg([
                       pl.col('temperature').mean().alias('mean_temp'),
                       pl.col('temperature').max().alias('max_temp'),
                       pl.col('temperature').min().alias('min_temp'),
                   ])
                   .sort(['month', 'mean_temp'], descending=True))
    
    # If not kwargs have been passed to the main function, just pull defaults.
    temp_col = kwargs.get('temp_col', 'mean_temp')
    top_n = kwargs.get('top_n', 10)
    flag_pct = kwargs.get('flag_pct', .3)

    event_day_day_flags = flag_extreme_days_pl(daily_temps, 
                                               temp_col=temp_col, 
                                               top_n=top_n, 
                                               flag_pct=flag_pct, 
                                               seed=random_seed)

    return (test_inputs
            .join(event_day_day_flags.select(['date', 'event_day_flag']), 
                  on=['date'], 
                  how='left')
            .with_columns(pl.coalesce(pl.col('event_day_flag'), pl.lit(0)).cast(pl.Int8).alias('event_day_flag'))
            .select('site_id', 'datetime', 'observed', 'temperature', 'ghi', 'event_day_flag', 'outage_flag'))



def hex_to_rgb(hex_str):
    ''' Utility to convert HEX colors to RGB
        
    '''
    # Remove the leading '#' if it exists
    hex_str = hex_str.lstrip('#')
    
    # Handle shorthand hex like #FFF -> #FFFFFF
    if len(hex_str) == 3:
        hex_str = "".join([c*2 for c in hex_str])
        
    # Convert hex to integer chunks
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


def single_baseline_plot(df):
    '''
    Generates a plot of the observed and both unadjusted and adjusted baselines.
    '''


    adjust_color = '#50c878'
    adjust_rgb = hex_to_rgb(adjust_color)
    event_color = '#fff8dc'
    event_rgb = hex_to_rgb(event_color)

    adjust_period = {
        'start': df.filter(pl.col('adjust_hour_flag') == 1).select(pl.min('hour_ending')).item(),
        'end': df.filter(pl.col('adjust_hour_flag') == 1).select(pl.max('hour_ending')).item(),
        'label': 'Adjust Period',
        'color': f'rgba({adjust_rgb[0]}, {adjust_rgb[1]}, {adjust_rgb[2]}, 0.12)',
    }

    event_period = {
        'start': df.filter(pl.col('event_hour_flag') == 1).select(pl.min('hour_ending')).item(),
        'end': df.filter(pl.col('event_hour_flag') == 1).select(pl.max('hour_ending')).item(),
        'label': 'Event Period',
        'color': f'rgba({event_rgb[0]}, {event_rgb[1]}, {event_rgb[2]}, 0.80)',
    }

    series_style = {
            'Observed': {'col': 'event_observed', 'color': '#00816d', 'dash': 'solid', 'width': 2.5},
            'Adjusted Baseline': {'col': 'adjusted_baseline', 'color': '#ff9e25', 'dash': 'solid', 'width': 2},
            'Unadjusted Baseline': {'col': 'unadjusted_baseline', 'color': '#c9a227', 'dash': 'dot', 'width': 2}}

    site_id = df.select('site_id').unique().item()
    event_date = df.select('event_date').unique().item()
    raw_adjustment = df.select('raw_adjustment').unique().item()
    capped_adjustment = df.select('capped_adjustment').unique().item()


    fig = go.Figure()

    for name, style in series_style.items():
            fig.add_trace(go.Scatter(
                    x=df['hour_ending'],
                    y=df[style['col']],
                    name=name.replace('_', ' '),
                    mode='lines+markers',
                    line=dict(color=style['color'], dash=style['dash'], width=style['width']),
                    marker=dict(size=5)))

    for period in (adjust_period, event_period):
            fig.add_vrect(
                    x0=period['start'] - 0.5,
                    x1=period['end'] + 0.5,
                    fillcolor=period['color'],
                    line_width=0,
                    layer='below',
                    annotation_text=period['label'],
                    annotation_position='top left',
                    annotation=dict(font_size=11, font_color='rgba(0,0,0,0.6)'))
            
    fig.add_annotation(
        text=f'Uncapped Adj. {raw_adjustment:.0%}<br>Capped Adj. {capped_adjustment:.0%}',
        xref='paper', yref='paper',
        x=0.05, y=0.98,
        xanchor='left', yanchor='top',
        showarrow=False,
        align='left',
        font=dict(size=11, color='#1f1f1f'),
        bgcolor='rgba(255, 255, 255, 0.7)',
        # bordercolor='rgba(0, 0, 0, 0.15)',
        # borderwidth=1,
        # borderpad=4
        )



    fig.update_layout(
        title=f'{site_id} - Observed vs. Baselines - {event_date.strftime("%A, %B %d, %Y")}',
        xaxis_title='Hour Ending',
        yaxis_title='kW',
        xaxis=dict(tickmode='linear', tick0=1, dtick=1, range=[0.5, 24.5]),
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified',
        width=900,
        height=500)
    
    fig.show()
