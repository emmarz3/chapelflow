"""
Settings for TESTING ChapelFlow on Render's free tier. NOT for real users.
Celery runs tasks inline because free Render has no always-on worker/beat --
so scheduled jobs (reminders, scheduled announcements) do NOT run here.
"""
from .production import *  # noqa

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False
