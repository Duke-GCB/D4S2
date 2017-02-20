from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Group


class Command(BaseCommand):
    help = 'Registers a user id for D4S2 and grants membership in named groups.'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Fully qualified username, e.g. netid@duke.edu')
        parser.add_argument('group_names', nargs='+', type=str, help='List of group names to add user to, e.g. '
                                                                     'informatics. Groups will be created as needed.')

    def _print_header(self, username, group_names):
        formatted_group_names = ', '.join(["'{}'".format(name) for name in group_names])
        self.stdout.write("Registering user '{}' with groups {}".format(username, formatted_group_names))

    def _get_or_create_user(self, username):
        user, created = User.objects.get_or_create(username=username)
        if created:
            self.stdout.write("User '{}' created ith id {}".format(username, user.id))
        else:
            self.stderr.write("User '{}', already exists with id {}".format(username, user.id))
        return user

    def _add_user_to_groups(self, user, group_names):
        for group_name in group_names:
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write("Group '{}' created ith id {}".format(group_name, group.id))
            else:
                self.stderr.write("Group '{}', already exists with id {}".format(group_name, group.id))
            try:
                if user in group.user_set.all():
                    self.stderr.write("User '{}' already a member of group '{}'".format(user.username, group_name))
                else:
                    group.user_set.add(user)
                    self.stdout.write("Added user '{}' to group '{}'".format(user.username, group_name))
            except Exception as e:
                raise CommandError(e)

    def handle(self, *args, **options):
        username = options['username']
        group_names = options['group_names']
        self._print_header(username, group_names)
        user = self._get_or_create_user(username)
        self._add_user_to_groups(user, group_names)


