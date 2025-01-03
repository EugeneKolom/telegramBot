import paramiko

# Генерация нового RSA-ключа
key = paramiko.RSAKey.generate(4096)

# Сохранение приватного ключа
private_key_path = "id_rsa"
with open(private_key_path, "w") as private_key_file:
    key.write_private_key(private_key_file)
    print(f"Приватный ключ сохранён: {private_key_path}")

# Сохранение публичного ключа
public_key_path = "id_rsa.pub"
with open(public_key_path, "w") as public_key_file:
    public_key_file.write(f"{key.get_name()} {key.get_base64()}")
    print(f"Публичный ключ сохранён: {public_key_path}")