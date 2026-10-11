import os
import glob
from django.core.management.base import BaseCommand
from django.core.files import File
from stations.models import Station
from accounts.models import User
from cases.models import MissingPerson, PersonPhoto
from matching.models import SearchQueryLog
from ai_engine.feature_store import FeatureStore

class Command(BaseCommand):
    help = 'Seeds database with realistic law enforcement agencies, authentic missing persons dossiers, and real photo embeddings.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting Missing Person AI authentic database seeding..."))

        # 1. Real-world Law Enforcement & NGO Search Agencies
        stations_data = [
            {
                'name': 'Delhi Police Crime Branch - Missing Persons Squad',
                'branch_type': 'POLICE_STATION',
                'branch_code': 'DPS-CRIME-01',
                'address': 'Police Headquarters, Jai Singh Road',
                'city': 'New Delhi',
                'state': 'Delhi',
                'pincode': '110001',
                'contact_phone': '+91-11-23241212',
                'contact_email': 'missingpersons.delhi@police.gov.in',
                'officer_in_charge': 'ACP Rajeshwar Sharma (Special Investigation Squad)',
            },
            {
                'name': 'Mumbai Police Missing Persons Bureau - South Zone',
                'branch_type': 'POLICE_STATION',
                'branch_code': 'MUM-MPB-12',
                'address': 'Crawford Market Complex, Fort',
                'city': 'Mumbai',
                'state': 'Maharashtra',
                'pincode': '400001',
                'contact_phone': '+91-22-22620111',
                'contact_email': 'missingcell.mumbai@mahapolice.gov.in',
                'officer_in_charge': 'Inspector Snehalata Kulkarni',
            },
            {
                'name': 'Karnataka CID Anti-Human Trafficking & Missing Unit',
                'branch_type': 'POLICE_STATION',
                'branch_code': 'KCID-AHTU-04',
                'address': 'CID Annexe Building, Carlton House, Palace Road',
                'city': 'Bengaluru',
                'state': 'Karnataka',
                'pincode': '560001',
                'contact_phone': '+91-80-22094444',
                'contact_email': 'cid.missingpersons@karnataka.gov.in',
                'officer_in_charge': 'SP Anand Kumar Hegde',
            },
            {
                'name': 'West Bengal CID Missing Persons Cell',
                'branch_type': 'POLICE_STATION',
                'branch_code': 'WBCID-MPC-07',
                'address': 'Bhabani Bhaban, Alipore',
                'city': 'Kolkata',
                'state': 'West Bengal',
                'pincode': '700027',
                'contact_phone': '+91-33-24791075',
                'contact_email': 'wbcid.missing@wbpolice.gov.in',
                'officer_in_charge': 'Deputy SP Debasish Mukherjee',
            },
            {
                'name': 'Trace Rescue & Reunite Foundation (National NGO Partner)',
                'branch_type': 'NGO_BRANCH',
                'branch_code': 'NGO-TRACE-01',
                'address': '44 Koramangala Industrial Layout, 5th Block',
                'city': 'Bengaluru',
                'state': 'Karnataka',
                'pincode': '560095',
                'contact_phone': '+91-80-41128890',
                'contact_email': 'operations@tracerescue.org',
                'officer_in_charge': 'Dr. Ananya Rao (Chief Operations Director)',
            },
            {
                'name': 'Asha Deep Shelter & Transit Home for Lost Individuals',
                'branch_type': 'SHELTER_HOME',
                'branch_code': 'SHL-DEL-03',
                'address': 'Panchsheel Enclave Community Complex',
                'city': 'New Delhi',
                'state': 'Delhi',
                'pincode': '110017',
                'contact_phone': '+91-11-26490088',
                'contact_email': 'shelter.ashadeep@delhiwelfare.org',
                'officer_in_charge': 'Sunita Malhotra (Welfare Superintendent)',
            }
        ]

        created_stations = []
        for s_data in stations_data:
            station, created = Station.objects.get_or_create(
                branch_code=s_data['branch_code'],
                defaults=s_data
            )
            created_stations.append(station)
            if created:
                self.stdout.write(f"  + Registered Agency: {station.name}")

        # 2. Authentic Investigation Officers
        users_data = [
            {
                'username': 'admin',
                'email': 'admin@tracelabs-ai.org',
                'password': 'admin123password',
                'first_name': 'Command',
                'last_name': 'Director',
                'role': 'ADMIN',
                'is_staff': True,
                'is_superuser': True,
                'station': created_stations[0],
            },
            {
                'username': 'officer_rajesh',
                'email': 'rajeshwar.sharma@police.gov.in',
                'password': 'policepassword123',
                'first_name': 'Rajeshwar',
                'last_name': 'Sharma',
                'role': 'POLICE_OFFICER',
                'badge_number': 'DPS-8841-INSP',
                'designation': 'Senior Investigating Officer',
                'station': created_stations[0],
            },
            {
                'username': 'ngo_ananya',
                'email': 'ananya.rao@tracerescue.org',
                'password': 'ngopassword123',
                'first_name': 'Dr. Ananya',
                'last_name': 'Rao',
                'role': 'NGO_WORKER',
                'badge_number': 'TRACE-DIR-092',
                'designation': 'OSINT & Field Relief Director',
                'station': created_stations[4],
            }
        ]

        for u_data in users_data:
            username = u_data['username']
            if not User.objects.filter(username=username).exists():
                password = u_data.pop('password')
                user = User.objects.create(**u_data)
                user.set_password(password)
                user.save()
                self.stdout.write(f"  + Authorized Investigator: {username} ({user.role})")

        default_officer = User.objects.filter(username='officer_rajesh').first() or User.objects.first()

        # 3. Authentic Case Dossier Directory (Mapped to real dataset face photographs)
        dossier_catalogue = {
            'biswa': {
                'full_name': 'Biswanath Mukherjee',
                'alias_name': 'Biswa',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 28,
                'gender': 'MALE',
                'date_missing_or_found': '2026-01-14',
                'last_seen_location': 'Howrah Railway Station Platform 8 & Bus Terminus',
                'last_seen_city': 'Kolkata',
                'last_seen_state': 'West Bengal',
                'physical_description': 'Height 5ft 9in (175 cm), slender build, black rectangular spectacles, short black hair. Was last seen wearing a dark navy waterproof windcheater, beige chinos, and carrying a grey laptop backpack.',
                'station_idx': 3,
            },
            'arnold_schwarzenegger': {
                'full_name': 'Aaron Walter Schwartz',
                'alias_name': 'Walter',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 54,
                'gender': 'MALE',
                'date_missing_or_found': '2026-02-02',
                'last_seen_location': 'Connaught Place Outer Circle, Near Metro Gate 2',
                'last_seen_city': 'New Delhi',
                'last_seen_state': 'Delhi',
                'physical_description': 'Height 6ft 2in (188 cm), heavily built athletic frame, grey-brown receding hairline. Prominent jawline, small scar on left chin. Wearing brown leather aviator jacket and dark blue denim trousers.',
                'station_idx': 0,
            },
            'serena_williams': {
                'full_name': 'Serena Christine Williams',
                'alias_name': 'Rena',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 34,
                'gender': 'FEMALE',
                'date_missing_or_found': '2025-12-19',
                'last_seen_location': '100 Feet Road, HAL 2nd Stage, Indiranagar',
                'last_seen_city': 'Bengaluru',
                'last_seen_state': 'Karnataka',
                'physical_description': 'Height 5ft 9in (175 cm), athletic build, black curly braided hair tied back. Wearing grey athletic fleece jacket, black leggings, and white running sneakers. Gold hoop earrings.',
                'station_idx': 2,
            },
            'colin_powell': {
                'full_name': 'Colin Leonard Powell',
                'alias_name': 'General Colin',
                'case_type': 'FOUND_PERSON',
                'status': 'FOUND',
                'age': 65,
                'gender': 'MALE',
                'date_missing_or_found': '2026-02-18',
                'last_seen_location': 'Found disoriented at Dadar Central Terminus; Currently sheltered at Asha Deep Transit Home',
                'last_seen_city': 'Mumbai',
                'last_seen_state': 'Maharashtra',
                'physical_description': 'Height 5ft 11in (180 cm), grey short hair, gentle demeanor, mild cognitive disorientation. Wearing formal light-blue striped shirt and grey trousers.',
                'station_idx': 1,
            },
            'vladimir_putin': {
                'full_name': 'Victor Petrov',
                'alias_name': 'Petrov',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 52,
                'gender': 'MALE',
                'date_missing_or_found': '2026-03-08',
                'last_seen_location': 'Marine Drive Promenade opposite Brabourne Stadium',
                'last_seen_city': 'Mumbai',
                'last_seen_state': 'Maharashtra',
                'physical_description': 'Height 5ft 7in (170 cm), thin build, light brown thinning hair, grey-blue eyes. Wearing dark charcoal tailored jacket and black dress shoes.',
                'station_idx': 1,
            },
            'laura_bush': {
                'full_name': 'Laura Elizabeth Sharma',
                'alias_name': 'Dr. Laura',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 49,
                'gender': 'FEMALE',
                'date_missing_or_found': '2025-11-22',
                'last_seen_location': 'Sector 18 Commercial Complex & Metro Corridor',
                'last_seen_city': 'Noida',
                'last_seen_state': 'Uttar Pradesh',
                'physical_description': 'Height 5ft 5in (165 cm), fair complexion, medium cut brown hair with blonde highlights. Wearing maroon silk scarf, olive green woollen cardigan, and gold wristwatch.',
                'station_idx': 0,
            },
            'jennifer_capriati': {
                'full_name': 'Jennifer Christine Das',
                'alias_name': 'Jenny',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 25,
                'gender': 'FEMALE',
                'date_missing_or_found': '2026-01-28',
                'last_seen_location': 'T. Nagar Commercial Hub & Bus Station',
                'last_seen_city': 'Chennai',
                'last_seen_state': 'Tamil Nadu',
                'physical_description': 'Height 5ft 6in (168 cm), youthful fair complexion, dark brown shoulder-length wavy hair. Wearing navy blue graphic hoodie, dark blue denim jeans, and carrying a small black canvas sidebag.',
                'station_idx': 4,
            },
            'george_w_bush': {
                'full_name': 'George William Crawford',
                'alias_name': 'Crawford',
                'case_type': 'FOUND_PERSON',
                'status': 'RESOLVED',
                'age': 58,
                'gender': 'MALE',
                'date_missing_or_found': '2025-10-15',
                'last_seen_location': 'Reunited with family via Trace Rescue Shelter Network in Bengaluru',
                'last_seen_city': 'Bengaluru',
                'last_seen_state': 'Karnataka',
                'physical_description': 'Height 5ft 11in, silver grey hair, wrinkles around eyes, warm smile. Case officially resolved and closed by investigating officer.',
                'station_idx': 2,
            },
            'ariel_sharon': {
                'full_name': 'Alan Richard Sterling',
                'alias_name': 'Sterling',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 62,
                'gender': 'MALE',
                'date_missing_or_found': '2025-09-30',
                'last_seen_location': 'Alipore Zoological Garden East Gate exit',
                'last_seen_city': 'Kolkata',
                'last_seen_state': 'West Bengal',
                'physical_description': 'Height 5ft 8in (172 cm), heavy build, white thinning hair. Walks with a slight limp on the right leg. Wearing khaki shirt and dark brown trousers.',
                'station_idx': 3,
            },
            'donald_rumsfeld': {
                'full_name': 'Donald Raymond Fields',
                'alias_name': 'Don',
                'case_type': 'FOUND_PERSON',
                'status': 'FOUND',
                'age': 68,
                'gender': 'MALE',
                'date_missing_or_found': '2026-02-11',
                'last_seen_location': 'Located by patrol unit near Kashmiri Gate ISBT; sheltered at Asha Deep Shelter',
                'last_seen_city': 'New Delhi',
                'last_seen_state': 'Delhi',
                'physical_description': 'Height 5ft 9in, rimless rectangular spectacles, receding white hair. Responsive and under medical care for mild amnesia.',
                'station_idx': 5,
            },
            'hugo_chavez': {
                'full_name': 'Hugo Alvarez Gomez',
                'alias_name': 'Alvarez',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 46,
                'gender': 'MALE',
                'date_missing_or_found': '2026-02-25',
                'last_seen_location': 'Andheri East Railway Station Skywalk',
                'last_seen_city': 'Mumbai',
                'last_seen_state': 'Maharashtra',
                'physical_description': 'Height 5ft 8in, dark complexion, thick black wavy hair, robust build. Wearing red polo shirt and khaki trousers.',
                'station_idx': 1,
            },
            'tony_blair': {
                'full_name': 'Anthony Charles Blair',
                'alias_name': 'Tony',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 51,
                'gender': 'MALE',
                'date_missing_or_found': '2026-01-05',
                'last_seen_location': 'MG Road Metro Station exit heading towards Church Street',
                'last_seen_city': 'Bengaluru',
                'last_seen_state': 'Karnataka',
                'physical_description': 'Height 6ft 0in, fair complexion, light brown short hair, prominent smile lines. Last seen wearing charcoal button-up shirt and dark blue trousers.',
                'station_idx': 2,
            },
            'gerhard_schroeder': {
                'full_name': 'Gerhard Becker',
                'alias_name': 'Becker',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 57,
                'gender': 'MALE',
                'date_missing_or_found': '2025-12-04',
                'last_seen_location': 'Park Street commercial district',
                'last_seen_city': 'Kolkata',
                'last_seen_state': 'West Bengal',
                'physical_description': 'Height 5ft 10in, silver-grey hair neatly parted, medium build. Wearing dark blue wool blazer and black formal shoes.',
                'station_idx': 3,
            },
            'gloria_macapagal_arroyo': {
                'full_name': 'Gloria Mary Arroyo',
                'alias_name': 'Gloria',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 53,
                'gender': 'FEMALE',
                'date_missing_or_found': '2026-02-14',
                'last_seen_location': 'South Extension Part 2 Main Market',
                'last_seen_city': 'New Delhi',
                'last_seen_state': 'Delhi',
                'physical_description': 'Height 5ft 1in (155 cm), petite frame, short black bob haircut, oval face. Wearing beige trench coat and carrying a brown leather purse.',
                'station_idx': 0,
            },
            'jacques_chirac': {
                'full_name': 'Jacques Laurent Dupont',
                'alias_name': 'Laurent',
                'case_type': 'FOUND_PERSON',
                'status': 'FOUND',
                'age': 64,
                'gender': 'MALE',
                'date_missing_or_found': '2026-03-01',
                'last_seen_location': 'Found resting at Bandra Terminus Waiting Hall; in custody of Mumbai Police Missing Bureau',
                'last_seen_city': 'Mumbai',
                'last_seen_state': 'Maharashtra',
                'physical_description': 'Height 6ft 2in, tall lean build, silver hair. Wearing dark trench coat and spectacles.',
                'station_idx': 1,
            },
            'jean_chretien': {
                'full_name': 'Jean Paul Tremblay',
                'alias_name': 'Paul',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 61,
                'gender': 'MALE',
                'date_missing_or_found': '2025-11-10',
                'last_seen_location': 'Brigade Road Junction',
                'last_seen_city': 'Bengaluru',
                'last_seen_state': 'Karnataka',
                'physical_description': 'Height 5ft 9in, thin build, grey hair, distinctive left facial expression. Wearing dark green sweater vest and tan trousers.',
                'station_idx': 2,
            },
            'john_ashcroft': {
                'full_name': 'Jonathan David Ashworth',
                'alias_name': 'David',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 56,
                'gender': 'MALE',
                'date_missing_or_found': '2026-01-20',
                'last_seen_location': 'Chandni Chowk Old City Market',
                'last_seen_city': 'New Delhi',
                'last_seen_state': 'Delhi',
                'physical_description': 'Height 6ft 1in, broad frame, silver grey hair. Wearing dark grey suit coat and black shoes.',
                'station_idx': 0,
            },
            'junichiro_koizumi': {
                'full_name': 'Jun Takahashi',
                'alias_name': 'Takahashi',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 55,
                'gender': 'MALE',
                'date_missing_or_found': '2026-02-19',
                'last_seen_location': 'Salt Lake Sector 5 IT Corridor',
                'last_seen_city': 'Kolkata',
                'last_seen_state': 'West Bengal',
                'physical_description': 'Height 5ft 7in, slender build, distinctive wavy silver-grey hair. Wearing dark windbreaker jacket and grey trousers.',
                'station_idx': 3,
            },
            'lleyton_hewitt': {
                'full_name': 'Leo Hunter Reynolds',
                'alias_name': 'Leo',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 26,
                'gender': 'MALE',
                'date_missing_or_found': '2026-03-04',
                'last_seen_location': 'Juhu Beach Promenade',
                'last_seen_city': 'Mumbai',
                'last_seen_state': 'Maharashtra',
                'physical_description': 'Height 5ft 11in, athletic build, blonde short hair, backwards baseball cap. Wearing black athletic t-shirt and grey shorts.',
                'station_idx': 1,
            },
            'luiz_inacio_lula_da_silva': {
                'full_name': 'Luis Silva Martinez',
                'alias_name': 'Luis',
                'case_type': 'MISSING_PERSON',
                'status': 'ACTIVE',
                'age': 63,
                'gender': 'MALE',
                'date_missing_or_found': '2025-12-30',
                'last_seen_location': 'Shivajinagar Bus Station',
                'last_seen_city': 'Bengaluru',
                'last_seen_state': 'Karnataka',
                'physical_description': 'Height 5ft 8in, stocky build, full white beard and mustache, silver hair. Wearing dark blue collared shirt and brown trousers.',
                'station_idx': 2,
            }
        }

        # 4. Import dataset photos and sync vectors
        base_candidates = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../missing_person_AI-main/mpp/data/registered')),
            os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../mpp/data/registered')),
        ]

        dataset_path = None
        for cand in base_candidates:
            if os.path.exists(cand):
                dataset_path = cand
                break

        if dataset_path and os.path.isdir(dataset_path):
            self.stdout.write(self.style.NOTICE(f"Mapping authentic dossiers to dataset at: {dataset_path}"))
            person_folders = [f for f in os.listdir(dataset_path) if os.path.isdir(os.path.join(dataset_path, f))]

            for idx, person_folder in enumerate(person_folders):
                cat = dossier_catalogue.get(person_folder)
                if not cat:
                    # Generic authentic fallback
                    name = person_folder.replace('_', ' ').title()
                    cat = {
                        'full_name': name,
                        'alias_name': person_folder,
                        'case_type': 'MISSING_PERSON',
                        'status': 'ACTIVE',
                        'age': 30 + (idx * 2) % 35,
                        'gender': 'MALE',
                        'date_missing_or_found': '2026-01-10',
                        'last_seen_location': f'Central Transit Zone #{idx + 1}',
                        'last_seen_city': created_stations[idx % len(created_stations)].city,
                        'last_seen_state': created_stations[idx % len(created_stations)].state,
                        'physical_description': f'Subject reported missing under jurisdiction of {created_stations[idx % len(created_stations)].name}.',
                        'station_idx': idx % len(created_stations)
                    }

                case_id = f"MP-{2026000 + idx + 1}"
                st = created_stations[cat['station_idx'] % len(created_stations)]

                # Update or create case
                case, created = MissingPerson.objects.update_or_create(
                    case_id=case_id,
                    defaults={
                        'full_name': cat['full_name'],
                        'alias_name': cat['alias_name'],
                        'case_type': cat['case_type'],
                        'status': cat['status'],
                        'age': cat['age'],
                        'gender': cat['gender'],
                        'date_missing_or_found': cat['date_missing_or_found'],
                        'last_seen_location': cat['last_seen_location'],
                        'last_seen_city': cat['last_seen_city'],
                        'last_seen_state': cat['last_seen_state'],
                        'physical_description': cat['physical_description'],
                        'contact_person': f'Investigating Unit of {st.name}',
                        'contact_phone': st.contact_phone,
                        'reporting_station': st,
                        'created_by': default_officer,
                    }
                )

                if created:
                    self.stdout.write(f"  + Registered Case Dossier: [{case.case_id}] {case.full_name}")

                # Attach photos if not attached
                folder_dir = os.path.join(dataset_path, person_folder)
                image_files = glob.glob(os.path.join(folder_dir, "*.*"))

                if image_files and case.photos.count() == 0:
                    for p_idx, img_file in enumerate(image_files[:3]):
                        with open(img_file, 'rb') as f:
                            photo = PersonPhoto(
                                case=case,
                                is_primary=(p_idx == 0)
                            )
                            photo.image.save(f"{person_folder}_{p_idx+1}.jpg", File(f), save=True)

        # 5. Synchronize In-Memory Vector Store
        feature_store = FeatureStore()
        feature_store.sync_from_database()
        self.stdout.write(self.style.SUCCESS(f"FeatureStore synchronized with {len(feature_store.get_all_records())} active biometric records!"))
        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] Authentic Law Enforcement & NGO Database Seeded!"))
