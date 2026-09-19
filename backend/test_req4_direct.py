import requests

def test_status_codes():
    print("=" * 60)
    print(" REQUIREMENT 4.4: DIRECT HTTP STATUS CODE CHECKS")
    print("=" * 60)

    # 1. Unauthenticated checks
    r1 = requests.get('http://127.0.0.1:8000/api/v1/reports')
    r2 = requests.patch('http://127.0.0.1:8000/api/v1/reports/27/verify')
    print(f"1. Unauthenticated GET /reports:           {r1.status_code} (detail: {r1.json().get('detail')})")
    print(f"2. Unauthenticated PATCH /reports/id/verify: {r2.status_code} (detail: {r2.json().get('detail')})")
    assert r1.status_code == 401
    assert r2.status_code == 401

    # 2. Citizen token checks
    login_c = requests.post('http://127.0.0.1:8000/api/v1/auth/login', json={'email': 'citizen_test_w5@example.com', 'password': 'testpassword123'}).json()
    cit_token = login_c['access_token']
    headers_c = {'Authorization': f'Bearer {cit_token}'}

    r3 = requests.get('http://127.0.0.1:8000/api/v1/reports', headers=headers_c)
    r4 = requests.patch('http://127.0.0.1:8000/api/v1/reports/27/verify', headers=headers_c)
    print(f"3. Citizen GET /reports:                   {r3.status_code} (detail: {r3.json().get('detail')})")
    print(f"4. Citizen PATCH /reports/id/verify:         {r4.status_code} (detail: {r4.json().get('detail')})")
    assert r3.status_code == 403
    assert r4.status_code == 403

    # 3. Municipal Officer checks (Authorized)
    login_o = requests.post('http://127.0.0.1:8000/api/v1/auth/login', json={'email': 'officer_test_w5@example.com', 'password': 'testpassword123'}).json()
    off_token = login_o['access_token']
    headers_o = {'Authorization': f'Bearer {off_token}'}

    r5 = requests.get('http://127.0.0.1:8000/api/v1/reports', headers=headers_o)
    print(f"5. Municipal Officer GET /reports:          {r5.status_code} (Returned {len(r5.json())} reports)")
    assert r5.status_code == 200

    # 4. Filter check (status and priority combined)
    r6 = requests.get('http://127.0.0.1:8000/api/v1/reports?status=submitted&priority=HIGH', headers=headers_o)
    print(f"6. Officer Filter ?status=submitted&priority=HIGH: {r6.status_code} (Returned {len(r6.json())} matches)")
    assert r6.status_code == 200

    print("=" * 60)
    print(" ALL DIRECT STATUS CODE CHECKS PASSED (100%)")
    print("=" * 60)

if __name__ == '__main__':
    test_status_codes()
