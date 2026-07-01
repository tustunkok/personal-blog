from fastapi import Request


def get_scheduler(request: Request):
    return request.app.state.scheduler
