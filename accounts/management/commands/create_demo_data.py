from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from companies.models import Company, Department
from files.models import Folder

User = get_user_model()


class Command(BaseCommand):
    help = 'Crée des données de démonstration (une seule fois si aucun utilisateur)'

    def handle(self, *args, **options):
        # Si des utilisateurs existent déjà, ne rien recréer
        if User.objects.exists():
            self.stdout.write('Utilisateurs déjà présents — données démo non recréées.')
            return

        self.stdout.write('Création des données de démonstration...')

        company, _ = Company.objects.get_or_create(
            slug='acme-corp',
            defaults={
                'name': 'ACME Corporation',
                'description': 'Entreprise de démonstration',
                'storage_quota_gb': 500,
            }
        )
        self.stdout.write(f'  Entreprise: {company.name}')

        dept_it, _ = Department.objects.get_or_create(
            company=company, name='Informatique',
            defaults={'description': 'Département IT', 'storage_quota_mb': 51200}
        )
        Department.objects.get_or_create(
            company=company, name='Ressources Humaines',
            defaults={'description': 'RH', 'storage_quota_mb': 20480}
        )

        admin = User.objects.create_user(
            email='admin@entreprise.be',
            password='admin1234',
            first_name='Admin',
            last_name='Système',
            role=User.Role.TECH_ADMIN,
            is_staff=True,
            is_superuser=True,
            company=company,
        )
        self.stdout.write(self.style.SUCCESS('  Admin: admin@entreprise.be / admin1234'))

        User.objects.create_user(
            email='directeur@entreprise.be',
            password='demo1234',
            first_name='Marie',
            last_name='Dupont',
            role=User.Role.COMPANY_ADMIN,
            company=company,
            storage_quota_mb=5120,
        )
        self.stdout.write('  Company Admin: directeur@entreprise.be / demo1234')

        manager = User.objects.create_user(
            email='manager@entreprise.be',
            password='demo1234',
            first_name='Jean',
            last_name='Martin',
            role=User.Role.MANAGER,
            company=company,
            department=dept_it,
            storage_quota_mb=2048,
        )
        dept_it.manager = manager
        dept_it.save()
        self.stdout.write('  Manager: manager@entreprise.be / demo1234')

        employee = User.objects.create_user(
            email='employe@entreprise.be',
            password='demo1234',
            first_name='Sophie',
            last_name='Bernard',
            role=User.Role.EMPLOYEE,
            company=company,
            department=dept_it,
            storage_quota_mb=1024,
        )
        self.stdout.write('  Employé: employe@entreprise.be / demo1234')

        Folder.objects.get_or_create(
            name='Documents', owner=employee, parent=None, department=dept_it
        )
        Folder.objects.get_or_create(
            name='Projets', owner=manager, parent=None, department=dept_it
        )

        self.stdout.write(self.style.SUCCESS('Données de démonstration créées avec succès !'))
