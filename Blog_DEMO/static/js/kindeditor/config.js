/**
 * Created by lau on 17-2-5.
 */
KindEditor.ready(function (K) {
    K.create('#textarea[name=content]',{
        width:'800px',
        height:'200px',
        uploadJson:'/admin/upload/Kindeditor',
    })
});