from django.db import models

class Station(models.Model):
    source_id = models.CharField(max_length=160, unique=True)
    name = models.CharField(max_length=250)
    address = models.CharField(max_length=500)
    city = models.CharField(max_length=150, blank=True)
    state = models.CharField(max_length=80, blank=True)
    latitude = models.FloatField(null=True, blank=True, db_index=True)
    longitude = models.FloatField(null=True, blank=True, db_index=True)
    price = models.DecimalField(max_digits=12, decimal_places=8)
    coordinate_source = models.CharField(max_length=100, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

class Geocode(models.Model):
    key = models.CharField(max_length=500, unique=True)
    result = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

class SavedPlan(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
