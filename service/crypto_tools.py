import argparse, os, secrets, sys
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from argon2 import PasswordHasher
from getpass import getpass
p=argparse.ArgumentParser(description='Utilitarios de demonstra??o')
p.add_argument('action',choices=['keygen','encrypt','decrypt','password-hash','password-verify','sign-keygen','sign','verify'])
p.add_argument('args',nargs='*'); a=p.parse_args()
if a.action=='keygen':
    if len(a.args)!=1: p.error('keygen <ficheiro-chave>')
    Path(a.args[0]).write_bytes(secrets.token_bytes(32)); os.chmod(a.args[0],0o600); print('Chave AES-256 criada')
elif a.action in ('encrypt','decrypt'):
    if len(a.args)!=3: p.error(f'{a.action} <entrada> <saida> <ficheiro-chave>')
    inp,out,key=map(Path,a.args); k=key.read_bytes()
    if len(k)!=32: sys.exit('A chave tem de ter 32 bytes')
    if a.action=='encrypt':
        nonce=secrets.token_bytes(12); cipher=AESGCM(k).encrypt(nonce,inp.read_bytes(),None); out.write_bytes(b'POC1'+nonce+cipher); print('Cifrado AES-256-GCM')
    else:
        raw=inp.read_bytes()
        if raw[:4]!=b'POC1': sys.exit('Formato inv?lido')
        try: plain=AESGCM(k).decrypt(raw[4:16],raw[16:],None)
        except Exception: sys.exit('Falha de autentica??o: chave errada ou ficheiro alterado')
        out.write_bytes(plain); print('Decifrado e autenticado')
elif a.action=='password-hash':
    ph=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
    print(ph.hash(getpass('Password de teste: ')))
elif a.action=='password-verify':
    if len(a.args)!=1: p.error('password-verify <hash-argon2id>')
    ph=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
    try:
        if ph.verify(a.args[0],getpass('Password de teste: ')): print('Password correta')
    except Exception: sys.exit('Password incorreta ou hash inv?lido')
elif a.action=='sign-keygen':
    if len(a.args)!=2: p.error('sign-keygen <chave-privada.pem> <chave-publica.pem>')
    priv=rsa.generate_private_key(public_exponent=65537,key_size=3072)
    Path(a.args[0]).write_bytes(priv.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    Path(a.args[1]).write_bytes(priv.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    os.chmod(a.args[0],0o600); print('Chave de assinatura separada criada (RSA-3072)')
elif a.action=='sign':
    if len(a.args)!=3: p.error('sign <documento> <assinatura> <chave-privada.pem>')
    priv=serialization.load_pem_private_key(Path(a.args[2]).read_bytes(),password=None)
    sig=priv.sign(Path(a.args[0]).read_bytes(),padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
    Path(a.args[1]).write_bytes(sig); print('Assinatura RSA-PSS/SHA-256 criada')
elif a.action=='verify':
    if len(a.args)!=3: p.error('verify <documento> <assinatura> <chave-publica.pem>')
    pub=serialization.load_pem_public_key(Path(a.args[2]).read_bytes())
    try: pub.verify(Path(a.args[1]).read_bytes(),Path(a.args[0]).read_bytes(),padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
    except Exception: sys.exit('ASSINATURA INV?LIDA: documento alterado ou assinatura errada')
    print('Assinatura v?lida')
