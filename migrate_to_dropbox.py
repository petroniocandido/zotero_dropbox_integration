#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime   # for key generation
import sqlite3					# 
import subprocess				# for executing bash comands
import re						# regular expression for test itemKey validity
import time
from enum import Enum
import numpy as np
import sys

charlist = '23456789ABCDEFGHIJKLMNPQRSTUVWXYZ'

global_key_increment = 12345

key_pattern = re.compile('['+charlist+']{8}')

file_path ='/home/petronio/dados/Dropbox/Referencias/'

class FieldType(Enum):
	Title = 1
	Url = 13


################################# 
## Integer to String in Base 36
#################################

def digit_to_char(digit):
    if digit < 10: return chr(ord('0') + digit)
    else: return chr(ord('a') + digit - 10)


def str_base(number,base):
    if number < 0:
        return '-' + str_base(-number,base)
    else:
        (d,m) = divmod(number,base)
        if d:
            return str_base(d,base) + digit_to_char(m)
        else:
            return digit_to_char(m)


def check_key(key):
	return key_pattern.match(key) is not None 
	

def generate_key():
	d = datetime.now()
	m = int(round(d.timestamp() * 1000))
	key = str_base(m, 36).upper()
	
	if not check_key(key):
		global global_key_increment
		global charlist
		cl = len(charlist)
		while not check_key(key):
			time.sleep(0.2)
			d = datetime.now()
			m = int(round(d.timestamp() * 1000)) + global_key_increment
			key = str_base(m, 36).upper()
			print("Trying new key {}".format(key))
			global_key_increment += 17
			
			for c in ['0','1','O']:
				nc = charlist[ np.random.randint(cl) ]
				key = key.replace(c,nc)
			
	return key
	

def execute_bash_command(bashCommand):
	path_to_bash = "/bin/bash"  # or whatever is appropriate
	process = subprocess.Popen(bashCommand, 
                           stdout=subprocess.PIPE, 
                           shell=True,
                           executable=path_to_bash)
	output, error = process.communicate()
	return output, error


def move_storage_files():
	bashCommand = "ls */* | while read i; do echo -n $i | xargs -I{} -0  mv {}  -t ~/dados/Dropbox/Referencias/ ; done"
	output,_ = execute_bash_command(bashCommand)
	print(output)
	
	
def backup_zotero_sqlite():
	output,_ = execute_bash_command("rm -rf zotero.sql.BAK")
	output,_ = execute_bash_command("cp zotero.sqlite zotero.sqlite.BAK")

	
def get_dropbox_link(filename):
	bashCommand = "dropbox sharelink Referencias/'{}'".format(filename)
	output, _ = execute_bash_command(bashCommand)
	
	return str(output, 'utf-8')
	

def create_connection():
	conn = sqlite3.connect('zotero.sqlite')
	return conn	


def close_connection(conn):
	conn.close()
	
	
def select_storage_attachment_items(conn):
	cursor = conn.cursor()
	cursor.execute("""SELECT itemID, parentItemID, contentType, path FROM itemAttachments 
	where linkmode in (0,1) and path like 'storage:%'""")
	
	return cursor
	
	
def insert_new_item(conn, debug=False):
	key = generate_key()
	cursor = conn.cursor()
	
	if debug:
		print("""INSERT INTO items (synced, itemTypeID, libraryID, version, key) VALUES ({},{},{},{},{})""".format(0, 2, 1, 0, key))
	else:
		cursor.execute("""INSERT INTO items (synced, itemTypeID, libraryID, version, key) VALUES (?,?,?,?,?)""", (0, 2, 1, 1, key))
	
	conn.commit()
	
	cursor = conn.cursor()
	
	if debug:
		print("""SELECT itemID from items where itemkey = {}""".format(key))
		id = 0
	else:
		cursor.execute("""SELECT itemID from items where key = ?""", (key,))
		id = cursor.fetchone()[0]
	
	#id = cursor.fetch() ??
	
	return (id, key)
	
	
def insert_new_data_value(conn, itemID, field_type, value):
	cursor = conn.cursor()
	cursor.execute("""INSERT INTO ItemDataValues(Value) Values(?)""", (value,))
	conn.commit()
	
	cursor = conn.cursor()
	cursor.execute("""SELECT max(valueID) FROM ItemDataValues""")
	valueID = cursor.fetchone()[0]
	
	cursor = conn.cursor()
	cursor.execute("""INSERT INTO ItemData(itemID, fieldID, valueID) Values(?,?,?)""",(itemID, field_type.value, valueID))
	conn.commit()
	

def delete_data_value(conn, itemID):
	
	cursor = conn.cursor()
	cursor.execute("""SELECT valueID FROM ItemData WHERE itemID = ?""",(itemID,))
	
	for line in cursor.fetchall():
		cursor.execute("""DELETE FROM ItemData WHERE valueID = ?""",line)
		cursor.execute("""DELETE FROM ItemDataValues WHERE valueID = ?""",line)

	conn.commit()
	
	
def update_attachment_item(conn, id, path, linkmode):
	cursor = conn.cursor()
	
	cursor.execute("""UPDATE itemAttachments SET path = ?, linkmode = ? WHERE itemID = ?""", (path, linkmode, id))
	
	conn.commit()
	

def insert_new_attachment_item(conn, id, parentItemID, contentType, path, linkmode, debug=False):
	key = generate_key()
	cursor = conn.cursor()
	
	cursor.execute("""INSERT INTO itemAttachments (itemID, parentItemID, contentType, path, linkmode) 
					VALUES (?,?,?,?,?)""", (id, parentItemID, contentType, path, linkmode))
	
	conn.commit()
	

def delete_attachment_item(conn, id):	
	cursor = conn.cursor()
	
	cursor.execute("""DELETE FROM itemAttachments WHERE itemID = ?""", (id, ))
	
	conn.commit()


def delete_item(conn, id):
	cursor = conn.cursor()
	
	cursor.execute("""DELETE FROM items where itemID = ?""", (id,))
	
	conn.commit()
	
	
def insert_deleted_item(conn, id):
	cursor = conn.cursor()
	
	cursor.execute("""INSERT INTO deletedItems (itemID) VALUES (?)""", (id,))
	
	conn.commit()
	

def create_dropboxlink(conn, parentItemID, path):
	url = get_dropbox_link(path)
			
	if "www.dropbox.com/s/" in url:
		
		id2, key = insert_new_item(conn)
		
		insert_new_data_value(conn, id2, FieldType.Title, "Dropbox URL - " + path)
		insert_new_data_value(conn, id2, FieldType.Url, url)
		
		insert_new_attachment_item(conn, id2, parentItemID, None, None, 3)
		
		print("Concluído com Exito !")
		
	else:
		print("Link do dropbox não criado ! {}".format(url))


def clear_storage(conn):
	
	backup_zotero_sqlite()
	
	cursor = select_storage_attachment_items(conn)
	
	for linha in cursor.fetchall():
		id_velho, parentItemID, contentType, path = linha
		insert_deleted_item(conn, id_velho)	
	
	
def migrar_storage(conn):
	
	backup_zotero_sqlite()
	
	cursor = select_storage_attachment_items(conn)
	
	for linha in cursor.fetchall():
		try:
			id_velho, parentItemID, contentType, path = linha
			
			print("Processando {}".format(path))
			
			delete_data_value(conn, id_velho)
			
			delete_attachment_item(conn, id_velho)
			
			delete_item(conn, id_velho)
			
			path = path.replace("storage:","")
			
			id1, key = insert_new_item(conn)
			
			insert_new_data_value(conn, id1, FieldType.Title, "Local Path - " + path)
			
			insert_new_attachment_item(conn, id1, parentItemID, contentType, file_path + path, 2)
			
			create_dropboxlink(conn, parentItemID, path)
			
		except Exception as ex:
			print("Erro em {}: {}".format(id_velho, ex))
			

def fix_dropbox_links(conn):
	
	backup_zotero_sqlite()
	
	cursor = conn.cursor()
	cursor.execute("""select DISTINCT parentItemID
from itemAttachments where parentItemID not in (
select parentItemID
from itemAttachments ita 
	join itemData as itd on ita.itemID = itd.itemID
	join itemdatavalues itdv on itd.valueid = itdv.valueid 
where itdv.value like 'Dropbox%' and itd.fieldID = 1)""")
	
	for line in cursor.fetchall():
		fix_dropbox_links_item(conn, line)


def fix_dropbox_links_item(conn, id):
	cursor = conn.cursor()
	cursor.execute("""select path from itemAttachments where parentItemID = ?""",id)
	path = cursor.fetchone()[0]
	
	url = str(path).replace(file_path, '')
	
	print(url)
	
	create_dropboxlink(conn, id[0], url)
	

print("========================================================================")
print("=== 				SISTEMA DE INTEGRAÇÃO ZOTERO-DROPBOX		 	===")
print("========================================================================\n\n\n\n")
print("\t1 - Migração física dos arquivos do storage para o dropbox (execute na pasta do storage)\n")
print("\t2 - Inclusão dos links para os arquivos no dropbox\n")
print("\t3 - Limpeza dos links dos arquivos do storage\n")
print("\t4 - Consertar links Dropbox faltantes\n")
print("\t5 - Sair\n")

op = input("Entre com a opção desejada:")
print(op)

if op == "1":
	op = input("Antes de continuar, essa opção deve ser executada dentro da pasta storage. Deseja continuar? (s/n)")
	if op == "s":
		move_storage_files()
	else:
		sys.exit(0)
elif op == "2":
	conn = create_connection()	
	migrar_storage(conn)
	close_connection(conn)
	
elif op == "3":
	conn = create_connection()	
	clear_storage(conn)
	close_connection(conn)
elif op == "4":
	conn = create_connection()	
	fix_dropbox_links(conn)
	close_connection(conn)

	
sys.exit(0)	



