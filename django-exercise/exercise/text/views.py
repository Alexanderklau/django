from django.shortcuts import render
from django.contrib.auth.models import User
from django.http import request,HttpResponse
from .forms import PublisherForm
from .models import Publiser
def hello(request,a):
    # print(request.GET.get('key'))
    user_list = User.objects.all()
    print(user_list.query)
    return render(request,'table.html',{'user_list':user_list})
# Create your views here.

def add_Publisher(request):
    if request.method == 'POST':
        publisher_form = PublisherForm(request.POST)
        if publisher_form.is_valid():
            Publiser.objects.create(
            company_name=publisher_form.cleaned_data['company_name'],
            company_address = publisher_form.cleaned_data['company_address'],
            company_city = publisher_form.cleaned_data['company_city'],
            company_web = publisher_form.cleaned_data['company_web'],
            )
            return HttpResponse('GOOD IDEAR!')
    else:
        publisher_form = PublisherForm()
    return render(request,'add_Publisher.html',locals())