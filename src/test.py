from utils import convert_acc_rpm_revs, convert_vel_rpm_revs

val1 = 1 << 8
val2 = 1 << 4

temp2 = convert_vel_rpm_revs(60)
temp = convert_acc_rpm_revs(60)

a = 10