from django.http import HttpResponse

def home(request,id):
    #print (dir(request))
    return HttpResponse("id is %s" %id)
def test(request,id):
    return HttpResponse("oh,new id is %s" %id)