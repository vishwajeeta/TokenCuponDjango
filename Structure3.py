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

class WalletTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=10, choices=[('credit', 'Credit'), ('debit', 'Debit')])
    reason = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.type} ₹{self.amount}"


### admin.py
from django.contrib import admin
from .models import UserWallet, TokenCreditLog, WalletTransaction

admin.site.register(UserWallet)
admin.site.register(TokenCreditLog)
admin.site.register(WalletTransaction)


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
from .models import UserWallet, TokenCreditLog, WalletTransaction
from django.contrib import messages
from decimal import Decimal
import qrcode
from io import BytesIO
import base64

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

                WalletTransaction.objects.create(
                    user=request.user,
                    amount=log.value,
                    type='credit',
                    reason=f"Token {log.token_code} redeemed"
                )

                messages.success(request, f"₹{log.value} added to your wallet!")
        except TokenCreditLog.DoesNotExist:
            messages.error(request, "Invalid token.")
        return redirect('wallet')

    return render(request, 'apply_token_wallet.html')

@login_required
def wallet_view(request):
    wallet = UserWallet.objects.get(user=request.user)
    transactions = WalletTransaction.objects.filter(user=request.user).order_by('-timestamp')

    # Generate QR code of user ID (can be customized further)
    qr = qrcode.make(f"WALLET:{request.user.id}")
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return render(request, 'wallet.html', {'wallet': wallet, 'transactions': transactions, 'qr_code': img_str})


### utils.py
from .models import UserWallet, WalletTransaction

def deduct_wallet_amount(user, amount, reason="Purchase"): 
    wallet = UserWallet.objects.get(user=user)
    if wallet.balance >= amount:
        wallet.balance -= amount
        wallet.save()
        WalletTransaction.objects.create(user=user, amount=amount, type='debit', reason=reason)
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
<h2>Your Wallet</h2>
<p>Balance: ₹{{ wallet.balance }}</p>
<img src="data:image/png;base64,{{ qr_code }}" width="150" height="150" alt="QR Code"/>
<h3>Transaction History</h3>
<ul>
  {% for t in transactions %}
    <li>{{ t.timestamp }} - {{ t.type }} ₹{{ t.amount }} - {{ t.reason }}</li>
  {% empty %}
    <li>No transactions yet.</li>
  {% endfor %}
</ul>
<a href="{% url 'apply_token_to_wallet' %}">Redeem Token</a>


### urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('wallet/', views.wallet_view, name='wallet'),
    path('wallet/apply-token/', views.apply_token_to_wallet, name='apply_token_to_wallet'),
]


### requirements.txt additions
qrcode
Pillow


### Final Notes:
# - API version can be added using Django REST Framework (DRF)
# - QR Code contains the user ID, but you can include wallet balance or token info as encoded JSON if needed
# - Add wallet auto-deduction in your purchase flow by calling `deduct_wallet_amount()`
# - Run migrations after adding new models: `makemigrations` and `migrate`
