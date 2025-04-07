### models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class DiscountToken(models.Model):
    name = models.CharField(max_length=50, default="PromoToken")
    token_code = models.CharField(max_length=50, unique=True)
    value = models.PositiveIntegerField(help_text="Value in points")
    remaining_value = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.token_code})"

    def is_expiring_soon(self):
        return 0 <= (self.valid_to - timezone.now()).days <= 2

class TokenUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.ForeignKey(DiscountToken, on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True)
    discount_used = models.PositiveIntegerField(default=0)


### forms.py
from django import forms

class TokenApplyForm(forms.Form):
    token_code = forms.CharField(label="Enter your discount token")


### views.py
from django.shortcuts import redirect, render
from django.utils import timezone
from django.core.mail import send_mail
from .models import DiscountToken, TokenUsage
from .forms import TokenApplyForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

@login_required
def apply_token(request):
    now = timezone.now()
    form = TokenApplyForm(request.POST or None)
    message = ""
    if form.is_valid():
        token_code = form.cleaned_data['token_code']
        try:
            token = DiscountToken.objects.get(
                token_code__iexact=token_code,
                valid_from__lte=now,
                valid_to__gte=now,
                active=True
            )
            if TokenUsage.objects.filter(user=request.user, token=token).exists():
                message = "You've already used this token."
            else:
                request.session['token_id'] = token.id
                TokenUsage.objects.create(user=request.user, token=token, discount_used=0)
                message = f"Token '{token.name}' applied!"

                if token.is_expiring_soon():
                    send_mail(
                        'Your Token is Expiring Soon',
                        f"Hi {request.user.username}, your token '{token.token_code}' will expire on {token.valid_to}.",
                        'noreply@yourstore.com',
                        [request.user.email],
                        fail_silently=True,
                    )
        except DiscountToken.DoesNotExist:
            request.session['token_id'] = None
            message = "Invalid or expired token."

    return render(request, 'apply_token.html', {'form': form, 'message': message})

@login_required
def token_usage_history(request):
    usages = TokenUsage.objects.filter(user=request.user).select_related('token').order_by('-used_at')
    return render(request, 'token_history.html', {'usages': usages})


### utils.py
from .models import DiscountToken, TokenUsage

def get_token_discounted_total(request, cart_total):
    token_id = request.session.get('token_id')
    if token_id:
        try:
            token = DiscountToken.objects.get(id=token_id)
            discount = min(token.value, cart_total)
            final_price = cart_total - discount

            # Update token remaining value
            token.value -= discount
            token.save()

            # Track how much was used
            TokenUsage.objects.filter(token=token).update(discount_used=discount)
            return final_price
        except DiscountToken.DoesNotExist:
            pass
    return cart_total


### apply_token.html
<form method="post">
  {% csrf_token %}
  {{ form.as_p }}
  <button type="submit">Apply Token</button>
</form>
<p>{{ message }}</p>

<script>
function scanQRToken() {
  alert("QR scanning coming soon!");
}
</script>
<button onclick="scanQRToken()">Scan Token QR</button>

{% if request.session.token_id %}
  <img src="https://api.qrserver.com/v1/create-qr-code/?data={{ request.session.token_id }}&size=150x150" alt="Token QR Code" />
{% endif %}


### token_history.html
<h2>Token Usage History</h2>
<table>
  <thead>
    <tr>
      <th>Token</th>
      <th>Original Points</th>
      <th>Used</th>
      <th>Remaining</th>
      <th>Used At</th>
    </tr>
  </thead>
  <tbody>
    {% for usage in usages %}
    <tr>
      <td>{{ usage.token.token_code }}</td>
      <td>{{ usage.token.value|add:usage.discount_used }}</td>
      <td>{{ usage.discount_used }}</td>
      <td>{{ usage.token.value }}</td>
      <td>{{ usage.used_at }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
