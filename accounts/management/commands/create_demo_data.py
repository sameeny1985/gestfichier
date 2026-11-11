from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from companies.models import Company, Department, Group
from files.models import Folder, FileItem

User = get_user_model()


class Command(BaseCommand):
    help = 'Crée des données de démonstration pour GestFichier'

    def handle(self, *args, **options):
        self.stdout.write('Création des données de démonstration...')

        # Company
        company, _ = Company.objects.get_or_create(
            slug='acme-corp',
            defaults={
                'name': 'ACME Corporation',
                'description': 'Entreprise de démonstration',
                'storage_quota_gb': 500,
            }
        )
        self.stdout.write(f'  Entreprise: {company.name}')

        # Departments
        dept_it, _ = Department.objects.get_or_create(
            company=company, name='Informatique',
            defaults={'description': 'Département IT', 'storage_quota_mb': 51200}
        )
        dept_rh, _ = Department.objects.get_or_create(
            company=company, name='Ressources Humaines',
            defaults={'description': 'RH', 'storage_quota_mb': 20480}
        )

        # Users
        admin, created = User.objects.get_or_create(
            email='admin@entreprise.fr',
            defaults={
                'first_name': 'Admin',
                'last_name': 'Système',
                'role': User.Role.TECH_ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'company': company,
            }
        )
        if created:
            admin.set_password('admin1234')
            admin.save()
            self.stdout.write(self.style.SUCCESS('  Admin créé: admin@entreprise.fr / admin1234'))

        company_admin, created = User.objects.get_or_create(
            email='directeur@entreprise.fr',
            defaults={
                'first_name': 'Marie',
                'last_name': 'Dupont',
                'role': User.Role.COMPANY_ADMIN,
                'company': company,
                'storage_quota_mb': 5120,
            }
        )
        if created:
            company_admin.set_password('demo1234')
            company_admin.save()
            self.stdout.write('  Company Admin: directeur@entreprise.fr / demo1234')

        manager, created = User.objects.get_or_create(
            email='manager@entreprise.fr',
            defaults={
                'first_name': 'Jean',
                'last_name': 'Martin',
                'role': User.Role.MANAGER,
                'company': company,
                'department': dept_it,
                'storage_quota_mb': 2048,
            }
        )
        if created:
            manager.set_password('demo1234')
            manager.save()
            dept_it.manager = manager
            dept_it.save()
            self.stdout.write('  Manager: manager@entreprise.fr / demo1234')

        employee, created = User.objects.get_or_create(
            email='employe@entreprise.fr',
            defaults={
                'first_name': 'Sophie',
                'last_name': 'Bernard',
                'role': User.Role.EMPLOYEE,
                'company': company,
                'department': dept_it,
                'storage_quota_mb': 1024,
            }
        )
        if created:
            employee.set_password('demo1234')
            employee.save()
            self.stdout.write('  Employé: employe@entreprise.fr / demo1234')

        # Folders
        Folder.objects.get_or_create(
            name='Documents', owner=employee, parent=None, department=dept_it
        )
        Folder.objects.get_or_create(
            name='Projets', owner=manager, parent=None, department=dept_it
        )

        self.stdout.write(self.style.SUCCESS('Données de démonstration créées avec succès !'))
