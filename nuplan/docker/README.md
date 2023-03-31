Качаем [тут](https://www.nuscenes.org/nuplan) датасет и карты. В разделе Downloads нас интересует NuPlan v1.1 Dataset -> nuPlan Maps и nuPlan Mini Split. Остальное - основной датасет на полтора терабайта. Создаем папку "dataset" и распаковываем туда архивы. 
В папке dataset должны быть в итоге папки maps и nuplan-v1.1

Далее билдим докер
```scss /* или css */
docker build -t nuplan .
```


После этого, заходим в файл run_docker.sh и ищем строчку 
```scss /* или css */
-v /mnt/hdd5/NuPlan/dockerfiles/dataset:/nuplan-devkit/nuplan/dataset:rw
```
Путь до датасета "/mnt/hdd5/NuPlan/dockerfiles/dataset" нужно заменить на тот, который у вас на компьютере. 

Затем запускаем этот сценарий:
```scss /* или css */
bash run_docker.sh
```

Внутри контейнера:
```scss /* или css */
cd nuplan-devkit

bash set_env.sh
```
Это запустит установку среды nuplan'а. Как все закончится, запускаем юпитер ноутбук:
```scss /* или css */
bash run_jupyter.sh
```
