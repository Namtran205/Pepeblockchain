from django.shortcuts import render

import accounts.sql
import forum.sql
from accounts.models import User
from datetime import date


def index(request):
    user_id = request.session.get('user_id')

    if not user_id or user_id == 'None':
        # Khách
        context = {'is_authenticated': False}
        context['user_count'] = accounts.sql.user_count()

    else:
        # USER ĐÃ ĐĂNG NHẬP
        # Lấy coin từ DB (ORM)
        user_coins = 0
        can_checkin = True
        try:
            user = User.objects.get(pk=user_id)
            user_coins = user.coins or 0
            last_checkin = user.last_checkin
            if last_checkin:
                today = date.today()
                can_checkin = last_checkin != today
        except User.DoesNotExist:
            pass

        context = {
            'is_authenticated': True,
            'username': request.session.get('username'),
            'user_coins': user_coins,
            'can_checkin': can_checkin,
        }

    context['suggested_posts'] = forum.sql.posts_with_attachment(5)
    context['popular_posts'] = forum.sql.popular_posts(5)
    context['latest_posts'] = forum.sql.latest_posts(5)
    context['latest_tests'] = forum.sql.latest_tests(5)

    return render(request, 'home/index.html', context)


