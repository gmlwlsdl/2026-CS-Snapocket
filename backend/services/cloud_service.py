import json
import pymysql
import os
from core.s3 import s3_client, BUCKET_NAME

def export_mysql_to_s3():
    connection = pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        db=os.getenv('DB_NAME'),
        charset='utf8mb4'
    )
    
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            
            sql = "SELECT * FROM my_table" 
            cursor.execute(sql)
            rows = cursor.fetchall()
            
            if not rows:
                return {"status": "empty", "message": "S3로 보낼 데이터가 테이블에 없습니다."}
            
            data_to_send = json.dumps(rows, ensure_ascii=False, default=str)
            
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key='cloud_data/snapocket_backup.json', # S3에 보관될 폴더 경로와 파일명
                Body=data_to_send,
                ContentType='application/json'
            )
            
            return {"status": "success", "message": "성공적으로 MySQL 데이터를 S3 클라우드에 백업했습니다!"}
            
    except Exception as e:
        return {"status": "error", "message": f"전송 중 실패: {str(e)}"}
        
    finally:
        connection.close()