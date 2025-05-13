from flask import Flask, render_template, request
from datetime import datetime, timedelta, time
import pytz

app = Flask(__name__)

def convert_local_to_utc(date_time, tz_name):
    local_tz = pytz.timezone(tz_name)
    if isinstance(date_time, datetime):
        local_dt = local_tz.localize(date_time, is_dst=None)
    else:
        naive = datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")
        local_dt = local_tz.localize(naive, is_dst=None)
    return local_dt.astimezone(pytz.utc)

def convert_utc_to_local(utc_str, tz_name):
    utc_dt = datetime.strptime(utc_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc)
    local_tz = pytz.timezone(tz_name)
    return utc_dt.astimezone(local_tz)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        entry_level = int(request.form['entry_level'])
        apat_default_effective_days = int(request.form['apat_default_effective_days'])
        apat_effective_days = int(request.form['apat_effective_days'])
        timez = request.form['timezone']
        apat_pricing_closer_days = int(request.form['apat_pricing_closer_days'])
        apat_pricing_closer_time_str = request.form['apat_pricing_closer_time']
        cut_off_time = request.form['cut_off_time']
        start_input = request.form['start_date']

        output = []

        if entry_level == 0:
            start_dt = datetime.strptime(start_input, '%Y-%m-%d %H:%M:%S')
            utc_final_sub_time = convert_local_to_utc(start_dt, timez) + timedelta(days=apat_pricing_closer_days)

            og_start_date = convert_local_to_utc(datetime.combine(start_dt.date(), time(0, 0, 0)), timez)
            og_convered_time = og_start_date.time()

            dt_str = f"{start_dt.date()} {apat_pricing_closer_time_str}"
            local_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            max_sub_time = convert_local_to_utc(local_dt, timez)

            end_dt = start_dt + timedelta(days=apat_pricing_closer_days)
            apat_pricing_closer_dt = datetime.combine(end_dt.date(), og_convered_time)

            batch_date = datetime.combine(start_dt.date() + timedelta(days=apat_pricing_closer_days), max_sub_time.time()) + timedelta(seconds=1)
            min_sub_datetime = convert_local_to_utc(datetime.combine(start_dt.date(), time(0, 0, 0)), timez).replace(tzinfo=None)
            max_sub_datetime = datetime.combine(start_dt.date() + timedelta(days=apat_pricing_closer_days), max_sub_time.time())

            min_effective_date = datetime.combine(start_dt.date() + timedelta(days=apat_default_effective_days), time(0, 0, 0))
            max_effective_date = datetime.combine(apat_pricing_closer_dt.date() + timedelta(days=apat_effective_days), time(0, 0, 0))

            output.append({
                "Batch Date": batch_date,
                "Min Submission": min_sub_datetime,
                "Max Submission": max_sub_datetime,
                "Min Effective": min_effective_date,
                "Max Effective": max_effective_date
            })

        else:
            start_dt = datetime.strptime(start_input, '%Y-%m-%d %H:%M:%S')
            og_start_date = start_dt.date()

            start_dt_conv_str = f"{og_start_date} {apat_pricing_closer_time_str}"
            local_dt_st_dt = datetime.strptime(start_dt_conv_str, "%Y-%m-%d %H:%M:%S")
            utc_final_sub_time = convert_local_to_utc(local_dt_st_dt, timez) + timedelta(days=apat_pricing_closer_days)

            dt_str = f"{og_start_date} {cut_off_time}"
            local_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            cut_off_time_conv = convert_local_to_utc(local_dt, timez)

            start_dt = datetime.combine(og_start_date, utc_final_sub_time.time()).replace(tzinfo=None)
            end_dt = start_dt + timedelta(days=apat_pricing_closer_days)

            final_condition = False
            first_min_sub = None
            prev_batch = None
            entry_created = True

            while not final_condition:
                if start_dt.date() > end_dt.date():
                    if utc_final_sub_time.time() > cut_off_time_conv.time():
                        batch_date = datetime.combine(start_dt.date() - timedelta(days=1), utc_final_sub_time.time()).replace(tzinfo=None) + timedelta(seconds=1)
                        min_sub_datetime = prev_batch
                        max_sub_datetime = datetime.combine(start_dt.date() - timedelta(days=1), cut_off_time_conv.time()) - timedelta(seconds=1)
                        min_effective_date = datetime.combine(start_dt.date() + timedelta(days=1), time(0, 0, 0))
                    else:
                        entry_created = False
                    final_condition = True
                else:
                    batch_date = datetime.combine(start_dt.date(), cut_off_time_conv.time()).replace(tzinfo=None)
                    if start_dt.date() != end_dt.date() and not first_min_sub:
                        min_sub_datetime = convert_local_to_utc(datetime.combine(start_dt.date(), time(0, 0, 0)), timez).replace(tzinfo=None)
                        first_min_sub = min_sub_datetime
                    else:
                        min_sub_datetime = prev_batch
                    prev_batch = batch_date

                    max_sub_datetime = datetime.combine(start_dt.date(), cut_off_time_conv.time()).replace(tzinfo=None) - timedelta(seconds=1)
                    min_effective_date = datetime.combine(start_dt.date() + timedelta(days=1), time(0, 0, 0))

                    start_dt += timedelta(days=1)

                max_effective_date = min_effective_date if entry_level == 2 else datetime.combine(end_dt.date() + timedelta(days=apat_effective_days), time(0, 0, 0))

                if entry_created:
                    output.append({
                        "Batch Date": batch_date,
                        "Min Submission": min_sub_datetime,
                        "Max Submission": max_sub_datetime,
                        "Min Effective": min_effective_date,
                        "Max Effective": max_effective_date
                    })

        return render_template('results.html', results=output)

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
