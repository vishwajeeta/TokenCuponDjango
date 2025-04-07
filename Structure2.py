### models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UserWallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.user.username}'s Wallet - ₹{self.balance}"

class TokenCreditLog(models.Model):
    token_code = models.CharField(max_length=50, unique=True)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    credited_to = models.ForeignKey(User, on_delete=models.CASCADE)
    credited_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)
    expiry = models.DateTimeField()

    def is_expired(self):
        return timezone.now() > self.expiry


### admin.py
from django.contrib import admin
from .models import UserWallet, TokenCreditLog

admin.site.register(UserWallet)
admin.site.register(TokenCreditLog)


### signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserWallet

@receiver(post_save, sender=User)
def create_wallet(sender, instance, created, **kwargs):
    if created:
        UserWallet.objects.create(user=instance)


### views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import UserWallet, TokenCreditLog
from django.contrib import messages
from decimal import Decimal

@login_required
def apply_token_to_wallet(request):
    if request.method == 'POST':
        token = request.POST.get('token_code')
        try:
            log = TokenCreditLog.objects.get(token_code=token, credited_to=request.user, used=False)
            if log.is_expired():
                messages.error(request, "Token expired.")
            else:
                wallet = UserWallet.objects.get(user=request.user)
                wallet.balance += log.value
                wallet.save()

                log.used = True
                log.save()

                messages.success(request, f"₹{log.value} added to your wallet!")
        except TokenCreditLog.DoesNotExist:
            messages.error(request, "Invalid token.")
        return redirect('wallet')

    return render(request, 'apply_token_wallet.html')

@login_required
def wallet_view(request):
    wallet = UserWallet.objects.get(user=request.user)
    return render(request, 'wallet.html', {'wallet': wallet})


### utils.py
from .models import UserWallet

def deduct_wallet_amount(user, amount):
    wallet = UserWallet.objects.get(user=user)
    if wallet.balance >= amount:
        wallet.balance -= amount
        wallet.save()
        return True
    return False


### apply_token_wallet.html
<h3>Apply Token to Wallet</h3>
<form method="post">
  {% csrf_token %}
  <label>Enter Token:</label>
  <input type="text" name="token_code" required />
  <button type="submit">Apply</button>
</form>
{% for message in messages %}
<p>{{ message }}</p>
{% endfor %}


### wallet.html
<h2>Wallet</h2>
<p>Current Balance: ₹{{ wallet.balance }}</p>
<a href="{% url 'apply_token_to_wallet' %}">Apply Token</a>


### urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('wallet/', views.wallet_view, name='wallet'),
    path('wallet/apply-token/', views.apply_token_to_wallet, name='apply_token_to_wallet'),
]


### migrations + init
# Don't forget to run:
# python manage.py makemigrations
# python manage.py migrate
# And register signals in apps.py or __init__.py
