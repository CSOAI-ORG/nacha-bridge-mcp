import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server

F="1"+" "*93+"\n"+"5"+" "*49+"PPD"+" "*41+"\n"+"6"+" "*93+"\n"+"9"+" "*93
def test_parse():
    p=server.parse_nacha(F); assert p.entries==1; assert "PPD" in p.sec_codes
def test_validate():
    assert server.validate_nacha(F).valid
def test_govern():
    assert any("OFAC" in f for f in server.govern_ach(F).frameworks)
