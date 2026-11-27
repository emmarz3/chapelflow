from rest_framework.throttling import ScopedRateThrottle


class AdvertisingScopedRateThrottle(ScopedRateThrottle):
    """Allow a short advertiser cooldown without relaxing other app limits."""

    def parse_rate(self, rate):
        if rate and rate.endswith('/5min'):
            return int(rate.split('/', 1)[0]), 5 * 60
        return super().parse_rate(rate)
