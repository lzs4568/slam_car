#include "slam_car_yolo/mpp_jpeg_encoder.hpp"
#include <cstdio>

namespace slam_car_yolo {

bool MppJpegEncoder::init(int width, int height, int quality) {
    width_  = width;
    height_ = height;

    MPP_RET ret = mpp_create(&ctx_, &mpi_);
    if (ret != MPP_OK) {
        fprintf(stderr, "[MPP] mpp_create failed: %d\n", ret);
        return false;
    }

    ret = mpp_init(ctx_, MPP_CTX_ENC, MPP_VIDEO_CodingMJPEG);
    if (ret != MPP_OK) {
        fprintf(stderr, "[MPP] mpp_init MJPEG failed: %d\n", ret);
        return false;
    }

    ret = mpp_enc_cfg_init(&cfg_);
    if (ret != MPP_OK) {
        fprintf(stderr, "[MPP] mpp_enc_cfg_init failed: %d\n", ret);
        return false;
    }

    // MJPEG 只需宽高，不设高级 rate-control 参数
    mpp_enc_cfg_set_s32(cfg_, "prep:width",  width);
    mpp_enc_cfg_set_s32(cfg_, "prep:height", height);

    ret = mpi_->control(ctx_, MPP_ENC_SET_CFG, cfg_);
    if (ret != MPP_OK) {
        // 兼容旧版 MPP ( -6 = MPP_ERR_READ_BUF / 参数不支持 )
        fprintf(stderr, "[MPP] SET_CFG returned %d, trying fallback...\n", ret);
        // 尝试不设宽高
        mpp_enc_cfg_init(&cfg_);
        ret = mpi_->control(ctx_, MPP_ENC_SET_CFG, cfg_);
        if (ret != MPP_OK) {
            fprintf(stderr, "[MPP] SET_CFG still failed: %d\n", ret);
            return false;
        }
    }

    fprintf(stderr, "[MPP] HW JPEG encoder ready: %dx%d q=%d\n", width, height, quality);
    return true;
}

bool MppJpegEncoder::encode(const uint8_t* nv12_data, std::vector<uint8_t>& jpeg_out) {
    jpeg_out.clear();

    const size_t frame_size = width_ * height_ * 3 / 2;

    // ---- 分配 MppBuffer 并拷入 NV12 ----
    MppBuffer buf = nullptr;
    MPP_RET ret = mpp_buffer_get(nullptr, &buf, frame_size);
    if (ret != MPP_OK || !buf) {
        fprintf(stderr, "[MPP] buffer_get failed: %d\n", ret);
        return false;
    }
    void* buf_ptr = mpp_buffer_get_ptr(buf);
    memcpy(buf_ptr, nv12_data, frame_size);

    // ---- 构造 MppFrame ----
    MppFrame frame = nullptr;
    mpp_frame_init(&frame);
    mpp_frame_set_width(frame, width_);
    mpp_frame_set_height(frame, height_);
    mpp_frame_set_hor_stride(frame, width_);
    mpp_frame_set_ver_stride(frame, height_);
    mpp_frame_set_fmt(frame, MPP_FMT_YUV420SP);
    mpp_frame_set_eos(frame, 1);
    mpp_frame_set_buffer(frame, buf);

    ret = mpi_->encode_put_frame(ctx_, frame);
    mpp_frame_deinit(&frame);

    if (ret != MPP_OK) {
        mpp_buffer_put(buf);
        fprintf(stderr, "[MPP] encode_put_frame failed: %d\n", ret);
        return false;
    }

    // ---- 取编码结果 ----
    MppPacket packet = nullptr;
    ret = mpi_->encode_get_packet(ctx_, &packet);

    if (ret == MPP_OK && packet) {
        void* data = mpp_packet_get_pos(packet);
        size_t len  = mpp_packet_get_length(packet);
        jpeg_out.assign(static_cast<uint8_t*>(data), static_cast<uint8_t*>(data) + len);
        mpp_packet_deinit(&packet);
    }

    mpp_buffer_put(buf);
    return !jpeg_out.empty();
}

MppJpegEncoder::~MppJpegEncoder() {
    if (ctx_) {
        if (mpi_) mpi_->reset(ctx_);
        mpp_destroy(ctx_);
    }
    if (cfg_) mpp_enc_cfg_deinit(cfg_);
    ctx_ = nullptr;
    mpi_ = nullptr;
    cfg_ = nullptr;
}

}  // namespace slam_car_yolo
