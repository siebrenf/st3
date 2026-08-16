from time import sleep

from requests.exceptions import ConnectionError, JSONDecodeError  # noqa
from requests_ratelimiter import LimiterSession  # noqa

from st3.logging import logger

DEBUG = True


class Request:
    """
    Handles all API requests.
    Only one instance of this class should be used.
    """

    base_url = "https://api.spacetraders.io/v2/"
    rate_limit_codes = [
        429,  # too many requests
    ]
    ddos_protection_codes = [
        502,  # way too many requests
    ]
    ddos_protection_sleep = 210
    server_down_codes = [
        500,  # unexpected server error
        503,  # service unavailable
        504,  # gateway timeout
    ]
    server_down_sleep = 3

    def __init__(self):
        self.session = LimiterSession(
            per_second=2,
            limit_statuses=self.rate_limit_codes,
        )

    def __call__(
        self,
        method: str,
        endpoint: str,
        token: str = None,
        json: dict = None,
        params: dict = None,
    ):
        if method == "get":
            if params is None:
                params = {"page": 1, "limit": 20}
            method = self.session.get
        elif method == "post":
            method = self.session.post
        elif method == "patch":
            method = self.session.patch
        # elif method == "get_all":
        #     return self.get_all(endpoint, token)
        else:
            raise NotImplementedError
        url = self.base_url + endpoint
        headers = {
            "Accept": "application/json",
        }
        if json:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # debug spurious API calls
        if DEBUG:
            j = f"{json=}" if json else ""
            p = f"{params=}" if params and params.get("page", 1) != 1 else ""
            logger.debug(f"{endpoint=} {j} {p}")

        response = self._request_response(method, url, headers, json, params)

        # self._check_response(response, endpoint, json, params)

        return response

    def _request_response(self, method, url, headers, json=None, params=None):
        """Make the request until a response is given"""
        response = None
        while True:
            try:
                response = method(url, headers=headers, json=json, params=params)
            except ConnectionError as e:
                # Server is still processing the request. Patience...
                if DEBUG:
                    logger.debug(f"{type(e).__name__}: {e}")
                    endpoint = url[8:]
                    logger.debug(f"{method=} {endpoint=} {headers=} {json=} {params=}")
                sleep(0.01)
                continue
            try:
                resp_json = response.json()
            except JSONDecodeError as e:
                if DEBUG:
                    logger.debug(f"{type(e).__name__}: {e}")
                resp_json = {}
            status_code = response.status_code
            endpoint = url[8:]
            if status_code in [200, 201]:  # ok/created
                break
            elif status_code == 204:  # no-content
                if DEBUG:
                    logger.debug("204 no content:")
                    resp_json["request"] = endpoint
                    if json:
                        resp_json["json"] = json
                    resp_json["status_code"] = status_code
                    logger.debug(resp_json)
                break
            elif status_code in self.rate_limit_codes:
                logger.debug(resp_json.get("error", {}).get("message", resp_json))
                sleep(resp_json.get("error", {}).get("data", {}).get("retryAfter", 1))
            elif status_code in self.ddos_protection_codes:
                logger.warning(f"Error code {status_code}: {resp_json}")
                sleep(self.ddos_protection_sleep)
            elif status_code in self.server_down_codes:
                logger.warning(
                    f"Server down (error code {status_code}). "
                    f"Retrying in {self.server_down_sleep} sec"
                )
                sleep(self.server_down_sleep)
            # elif status_code // 100 == 4 and resp_json["error"]["code"] in [
            #     4000,
            #     4200,
            #     4214,
            # ]:
            #     logger.warning("desync event:")
            #     resp_json["request"] = endpoint
            #     if json:
            #         resp_json["json"] = json
            #     resp_json["status_code"] = status_code
            #     logger.warning(resp_json)
            #     # catch and wait out time desync errors
            #     error_code = resp_json["error"]["code"]
            #     if error_code == 4000:
            #         # cooldownConflictError: Ship action is still on cooldown
            #         t = resp_json["error"]["data"]["cooldown"]["remainingSeconds"]
            #     elif error_code == 4200:
            #         # navigateInTransitError
            #         raise NotImplementedError(
            #             "TODO: extract the time to arrival from resp_json:", resp_json
            #         )
            #     elif error_code == 4214:
            #         # shipInTransitError
            #         t = resp_json["error"]["data"]["secondsToArrival"]
            #     else:
            #         raise AssertionError("Unreachable code reached")
            #     sleep(t)
            elif status_code == 400:  # "error" in resp_json
                if DEBUG:
                    logger.debug("400 game error:")
                    resp_json["request"] = endpoint
                    if json:
                        resp_json["json"] = json
                    resp_json["status_code"] = status_code
                    logger.debug(resp_json)
                break
            else:
                # unknown status code
                if DEBUG:
                    logger.debug("unknown status code:")
                    resp_json["request"] = endpoint
                    if json:
                        resp_json["json"] = json
                    resp_json["status_code"] = status_code
                    logger.debug(resp_json)
                break
        return response

    # def _check_response(self, response, endpoint, json, params):
    #     status_code = response.status_code
    #     resp_json = response.json()
    #     if status_code in [200, 201]:
    #         pass
    #     elif status_code == 204:  # no-content
    #         if DEBUG:
    #             logger.debug(
    #                 f"204 no content. {status_code=} "
    #                 f"{endpoint=} {json=} {params=} {resp_json=}"
    #             )
    #     elif status_code == 400:  # "error" in resp_json
    #         if DEBUG:
    #             resp_json["request"] = endpoint
    #             if json:
    #                 resp_json["json"] = json
    #             resp_json["status_code"] = status_code
    #             logger.debug(resp_json)
    #     else:
    #         raise NotImplementedError(
    #             f"Unknown situation. {status_code=} "
    #             f"{endpoint=} {json=} {params=} {resp_json=}"
    #         )

    def get(self, endpoint, token=None, params=None):
        return self("get", endpoint, token, None, params)

    def post(self, endpoint, token=None, json=None):
        return self("post", endpoint, token, json)

    def patch(self, endpoint, token=None, json=None):
        return self("patch", endpoint, token, json)

    # def get_all(self, endpoint, token=None):
    #     """yield all results from the get request, not just the first 20 results."""
    #     total = 0
    #     page = 0
    #     while True:
    #         page += 1
    #         resp_json = self("get", endpoint, token, {"page": page, "limit": 20})
    #         yield resp_json
    #         total += len(resp_json["data"])
    #         if total == resp_json["meta"]["total"]:
    #             break
