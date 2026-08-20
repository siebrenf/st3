"""
Supervisor (unique):
- lock
- register PID
- while True:
    - monitor worker health
    - monitor worker CPU usage
    - spawn/kill workers if needed
    - sleep
- unlock
- deregister PID

Messenger (unique):
- register PID
- while not told to stop:
    - listen (with timeout)
    - read api requests
    - perform request
    - writes output + heartbeat
- deregister PID

Director (unique per agent):
- register PID + agent
- while not told to stop:
    - listen for idle ships/credit threshold/contract completed/ships needed (with timeout)
    - get game state + stats
      (start_system_escaped, credits/min, API request/min,
       n_traders, n_explorers, trade_systems,
       idle traders, idle explorers, idle probes, idle miners)
    - come up with top-level plans
      (trade in system A/mine in system A/explore system B/
       explore market(s) in system A/probe market/
       buy ship/upgrade ship/sell ship/contract)
    - write output + heartbeat
    - sleep 10?
- deregister PID

Worker:
- register PID
- while not told to stop:
    - listen (with timeout)
    - option 1:
        - read available plan
        - CPU heavy: convert plan into route with steps
          (navigate, refuel, repair, buy cargo, sell cargo, jettison cargo, supply, deliver, market, shipyard)
        - write route to routes + heartbeat
    - option 2:
        - read available steps of currently ready task
        - write api requests to queue + heartbeat
    - option 3:
        - read available steps of currently ready task
        - parse API response
        - write response to game state + update route + heartbeat
        - continue with option 2 if possible
    - option 4:
        - read available steps of currently ready task
        - CPU heavy: review options
        - update route + heartbeat
        - continue with option 2 if possible
- deregister PID
"""
