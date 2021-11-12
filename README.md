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
   "node01.main.local":"node01.replica.local",
   "node02.main.local":"node02.replica.local",
   "node03.main.local":"node03.replica.local"
}
```
