"""
Supervisor (unique):
- lock
- read config (agent prefix + account token + desired agent count)
- while True:
    - monitor worker health
    - monitor worker CPU usage
    - spawn/kill workers if needed
    - sleep 10
- unlock

Director (unique per agent):
- register PID + agent
- while not told to stop:
    - come up with top-level plans
    - writes output + heartbeat
- deregister PID

CPU worker:
- register PID
- while not told to stop:
    - listen (with timeout)
    - read available plans
    - convert into task with steps
    - writes output + heartbeat (+ track own cpu usage?)
- deregister PID

I/O worker (async):
- register PID
- start async loop (limited size)
- add continuous async heartbeat task to loop
(- add continuous async cpu usage measuring task to loop?)
- while not told to stop:
    - while loop has space:
        - listen (with timeout)
        - read available steps of currently ready task
        - writes api requests
        - await: read api response
        - update game state
        - update current task step
- deregister PID

messenger (unique):
- register PID
- while not told to stop:
    - listen (with timeout)
    - read api requests
    - perform request
    - writes output + heartbeat
- deregister PID
"""
