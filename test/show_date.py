# -*- coding: utf-8 -*-
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
font = FontProperties(fname=r"C:\Windows\Fonts\simhei.ttf", size=14)

plt.bar([0.8,2.8,4.8,6.8], [2.10, 1.70, 1.50, 3.89], label='three nodes',width=0.4)

plt.bar([1.2,3.2,5.2,7.2], [2.39, 2.39, 1.80, 4.39], label='four nodes',width=0.4)
plt.xticks([1,3,5,7],["registration","token\ngeneration\npreparation","token generation","login"],FontProperties=font)
x=[0.8,2.8,4.8,6.8,1.2,3.2,5.2,7.2]
y=[2.10, 1.70, 1.50, 3.89,2.39, 2.39, 1.80, 4.39]
plt.ylim(0,5)
for a,b in zip(x,y):
    plt.text(a,b+0.05,"%.2f"%b, ha='center', va= 'bottom',fontsize=7)
# params

# x: 条形图x轴
# y：条形图的高度
# width：条形图的宽度 默认是0.8
# bottom：条形底部的y坐标值 默认是0
# align：center / edge 条形图是否以x轴坐标为中心点或者是以x轴坐标为边缘

plt.legend()

plt.xlabel('phase', FontProperties=font)
plt.ylabel('time(ms)', FontProperties=font)

#plt.title(u'Time spent in each stage', FontProperties=font)

plt.show()