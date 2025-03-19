import time

homing_max_duration = 30
start_time = time.time()
elapsed_time = 0
while elapsed_time <= homing_max_duration:
    elapsed_time = time.time() - start_time
    time.sleep(5)
    print(f"Elapsed time {elapsed_time}")