# pve-autorepl
This script setup replication for VM which start on boot.

Этот скрипт ищет VM, которые стартуют автоматически, но не реплицируются. 
Если такие VM найдены, то скрипт:
* Отправляет письмо на email root пользователя
* Затем он настраивает репликацию для найденных VM

Карта репликаций (откуда -> куда) берется из файла: /root/Sync/replication-map.json
root@AX101-Helsinki-02:~# cat /root/Sync/replication-map.json
```
{
   "source-hostname-01":"target-hostname-01",
   "source-hostname-02":"target-hostname-02",
   "source-hostname-03":"target-hostname-03"
}
```
