from mongoengine import StringField, DateTimeField, Document, DynamicDocument, connect
import datetime


class ExtraData(DynamicDocument):
    title = StringField(max_length=200, required=True)
    date_modified = DateTimeField(default=datetime.datetime.utcnow)


def main():
    connect('test', host='127.0.0.1', port=27017)
    page = ExtraData(title='Using MongoEngine')
    page.tags = ['mongodb', 'mongoengine']
    page.save()

    count = ExtraData.objects(tags='mongoengine').count()
    print(count)


main()
