from django.shortcuts import render
from .models import Game_info
from django.core.paginator import Paginator
def index(request):
    limit = 20
    game_info = Game_info.objects[:20]
    paginator = Paginator(game_info,limit)
    page = request.GET.get('page',1)
    loaded = paginator.page(page)
    context = {
        'Gameinfo':loaded
    }
    return render(request,'index.html',context)
# Create your views here.
#     title = StringField()
#     star = StringField()
#     date = StringField()
#     ID = StringField()
#     type = StringField()