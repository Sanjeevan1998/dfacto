from apscheduler.schedulers.background import BackgroundScheduler
import database
from agents.workflow import run_crawler

scheduler = BackgroundScheduler()

def fetch_and_store_headlines():
    config = database.get_config()
    keywords = config.get("keywords")
    if not keywords:
        print("Scheduler: No keywords configured. Skipping...")
        return
        
    print(f"Scheduler: Starting crawler job for keywords: '{keywords}'")
    
    # Split the user input by commas to get individual phrases
    phrases = [k.strip() for k in keywords.split(',') if k.strip()]
    
    if not phrases:
        print("Scheduler: No valid phrases to process.")
        return

    # Clear old database records once at the start of the job
    database.clear_headlines()

    for phrase in phrases:
        print(f"Scheduler: Processing phrase: '{phrase}'...")
        headlines = run_crawler(phrase)
        if headlines:
            print(f"Scheduler: Found {len(headlines)} headlines for '{phrase}'. Saving to DB...")
            database.save_headlines(headlines, associated_keyword=phrase)
        else:
            print(f"Scheduler: No relevant headlines extracted for '{phrase}'.")

def start_scheduler():
    config = database.get_config()
    interval_minutes = config.get("timer_interval", 60)
    
    # Run once at startup
    scheduler.add_job(fetch_and_store_headlines, 'date')
    
    # Schedule recurring job
    scheduler.add_job(
        fetch_and_store_headlines, 
        'interval', 
        minutes=interval_minutes, 
        id='crawler_job', 
        replace_existing=True
    )
    scheduler.start()
    print(f"Started scheduler with interval of {interval_minutes} minutes.")

def update_job_interval(minutes: int):
    # Reschedule the job if it exists
    if scheduler.get_job('crawler_job'):
        scheduler.reschedule_job('crawler_job', trigger='interval', minutes=minutes)
        print(f"Rescheduled job to run every {minutes} minutes.")
    
def shutdown_scheduler():
    scheduler.shutdown()
