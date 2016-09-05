from django.shortcuts import render,redirect
from django.http import HttpResponse
from rango.models import Item
def home_page(request):
    if request.method == 'POST':
        Item.objects.create(text=request.POST['item_text'])
        return redirect('/')

    items = Item.objects.all()
    return render(request,'home.html',{'items':items})
        # Item.objects.create(text=new_item_text)
    # else:
    #     new_item_text = ''
    # return render(request,'home.html',{
    #     'new_item_text':new_item_text,
    # })
    # item = Item()
    # item.text = request.POST.get('item_text','')
    # item.save()
    # return render(request,'home.html',{
    #     'new_item_text':item.text
    #     'new_item_text':request.POST.get('item_text','')
    # })
    # return render(request,'home.html',{
    #     'new_item_text':request.POST.get('item_text',''),
    # })
    #return HttpResponse('<html><title>To-Do lists</title></html>')
# Create your views here.
