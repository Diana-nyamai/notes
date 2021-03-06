from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.status import HTTP_200_OK
from .models import Note, NoteUser
from .serializers import NoteSerializer, NoteUserSerializer, NoteSharedSerializer
from django.contrib.auth import get_user_model
User = get_user_model()


class NoteAPI(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NoteSerializer
    queryset = Note.objects.all()

    def get_queryset(self):
        queryset = self.queryset
        request_user = self.request.user

        # non-admins can only CRUD their notes
        if not (request_user.is_staff or request_user.is_admin):
            query_set = queryset.filter(owner=self.request.user)
            return query_set
        else:
            return queryset

    def list(self, request):
        queryset = Note.objects.all().filter(owner=request.user)
        serializer = NoteSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        # get shared_to
        try:
            self.shared_to = request.data["shared_to"]
        except Exception:
            pass
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        instance = serializer.save(owner=self.request.user)

        # save NoteUser instances (share the note)
        if self.shared_to and len(self.shared_to) > 0:

            shared_to_users = User.objects.filter(pk__in=self.shared_to)

            note_user_objects = []
            for usr in shared_to_users:
                if usr != instance.owner:
                    note_user_objects.append(
                        NoteUser(note=instance, user=usr))

            NoteUser.objects.bulk_create(note_user_objects)

        super().perform_create(serializer)

    def update(self, request, *args, **kwargs):
        if request.data["shared_to"]:
            self.shared_to = (request.data["shared_to"])

        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        instance = serializer.save()

        # save new NoteUser instances (share the note)
        if instance and self.shared_to and len(self.shared_to) > 0:
            shared_to_users = User.objects.filter(pk__in=self.shared_to)
            NoteUser.objects.filter(note=instance).delete()

            note_user_objects = []
            for usr in shared_to_users:
                if usr != instance.owner:
                    note_user_objects.append(
                        NoteUser(note=instance, user=usr))

            NoteUser.objects.bulk_create(note_user_objects)
        #
        super().perform_update(serializer)


class AllNoteUserAPI(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NoteUserSerializer
    queryset = NoteUser.objects.all()


class ShareNoteAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        note_id = self.kwargs['id']
        request_user = request.user

        # verify request_user isAdmin/isStaff or note belongs to user
        user_shared_notes = []
        if not request_user.is_staff and not request_user.is_admin and request_user != Note.objects.get(id=note_id).owner:
            raise PermissionDenied()
        else:
            user_shared_notes = NoteUser.objects.filter(
                note_id=note_id).select_related('user')

        # get all users with access with access to the note
        users_with_access = []
        for shared_note in user_shared_notes:
            users_with_access.append(
                {
                    "id": shared_note.user.id,
                    "username": shared_note.user.username,
                    "email": shared_note.user.email
                }
            )

        return Response(users_with_access)

    def post(self, request, *args, **kwargs):
        request_user = request.user
        note_id = self.kwargs['id']
        user = request.data['user_id']

        # verify note belongs to user or isAdmin/isStaff
        if not request_user.is_staff and not request_user.is_admin and request_user != Note.objects.get(id=note_id).owner:
            raise PermissionDenied()
        else:
            # share note
            try:
                note_user = NoteUser(user_id=user, note_id=note_id)
                note_user.save()
            except Exception as e:
                raise APIException(
                    'Something went wrong. Please try again. ' + str(e))
            else:
                return Response(status=HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        request_user = request.user
        note_id = self.kwargs['id']
        user = request.data['user_id']

        # verify note belongs to user or isAdmin/isStaff
        if not request_user.is_staff and not request_user.is_admin and request_user != Note.objects.get(id=note_id).owner:
            raise PermissionDenied()
        else:
            # remove user access to note
            try:
                note_user = NoteUser.objects.get(user_id=user, note_id=note_id)
                note_user.delete()
            except Exception as e:
                raise APIException(
                    'Something went wrong. Please try again. ' + str(e))
            else:
                return Response(status=HTTP_200_OK)


class NotesSharedWithUserAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        request_user = request.user

        notes_shared_with_user = [
            note_user.note for note_user in NoteUser.objects.filter(user=request_user)]

        serializer = NoteSharedSerializer(notes_shared_with_user, many=True)

        return Response(serializer.data)
