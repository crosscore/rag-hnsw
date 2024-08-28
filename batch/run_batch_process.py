# batch/run_batch_process.py
import subprocess
from datetime import datetime
from src.utils import setup_logging

logger = setup_logging("run_batch_process")

def run_process(script_name):
    logger.info(f"Starting {script_name}")
    process = subprocess.Popen(['python', f'src/{script_name}'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        logger.error(f"Error running {script_name}")
        logger.error(stderr.decode())
    else:
        logger.info(f"{script_name} completed successfully")
    logger.info(stdout.decode())

def main():
    start_time = datetime.now()
    logger.info(f"Batch process started at {start_time}")

    processes = ['drop_table.py', 'vectorizer.py', 'csv_to_aurora.py', 'toc_to_aurora.py']

    for process in processes:
        run_process(process)

    end_time = datetime.now()
    logger.info(f"Batch process completed at {end_time}")
    logger.info(f"Total execution time: {end_time - start_time}")

if __name__ == "__main__":
    main()
